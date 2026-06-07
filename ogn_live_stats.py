#!/usr/bin/python
"""
live_stats.py
Connects to one or two TCP ports receiving OGN/FLARM log lines and prints
rolling stats side by side to the console, with a target list below.

Usage:
    python live_stats.py --port 50001
    python live_stats.py --port 50001 --port2 50002 --title "Site A" --title2 "Site B"
"""

import re
import os
import socket
import argparse
import time
import threading
import csv
import json
from collections import deque

ddb = None
ddb_cache = dict()
home = (50.27286, 18.67223)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

LINE_RE = re.compile(
    r"""
    [\d.]+sec:
    [\d.]+MHz:\s+
    [\d:]+:(\w+)\s+                        # aircraft ID (1)
    \d+:\s+
    \[\s*([+-][\d.]+),\s*([+-][\d.]+)\]deg  # lat, lon (2, 3)
    \s+(\d+)m                               # altitude (m) (4)
    .*?
    ([\d.]+)/[\d.]+dB                       # SNR / noise (5)
    .*?
    ([\d.]+)km\s+[\d.]+deg                  # distance km (6)
    \s+[+-][\d.]+deg                        # elevation angle
    ([\s!?R]*)                              # optional flags: !, ?, R (7)
    """,
    re.VERBOSE,
)

LINE_RE2 = re.compile(
    r"""
    APRS\s<-\s(OGN|FNT|ICA|FLR|PAW)
    (\w+)>OG\w{3,4},q\w+:.                  # aircraft ID (2), dstcall
                                            # Relayed packets would have relay here, omitted by purpose
    \d+h                                    # time
    (\d{2})([\d.]+)(N|S).                   # latitude (3, 4, 5)
    (\d{3})([\d.]+)(E|W).                   # longitude (6, 7, 8)
    \d+/\d+/A=(\d+)\s+                      # altitude [ft] (9)
    .*?
    ([\d.]+)dB                              # SNR / noise (10)
    """,
    re.VERBOSE,
)


HARD_MAX_KM = 200



def sphere_dist(c1,c2):
    from math import sin, cos, sqrt, atan2, radians
    # Approximate radius of earth in km
    c1 = ( radians(c1[0]), radians(c1[1]) )
    c2 = ( radians(c2[0]), radians(c2[1]) )

    dlon = c2[1] - c1[1]
    dlat = c2[0] - c1[0]

    a = sin(dlat / 2)**2 + cos(c1[0]) * cos(c2[0]) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = 6371.0 * c
    return(distance)


def lookup_ognddb(id):
  global ddb
  global ddb_cache

  if id in ddb_cache:
    return ddb_cache[id]

  if ddb is None:
    try: 
      with open('ognddb.json', 'r') as file:
        ddb = json.load(file)['devices']
        file.close()
    except:
      print("Can't open ognddb.json")
      time.sleep(3)
      ddb = dict()

  res = None
  for e in ddb:
    if (e['device_id'] == id):
      if e['cn'] != '':
        res = e['cn']
        break
      elif len(e['registration']) >=2:
        res = e['registration']
        break
      else:
        res = None
        break

  ddb_cache[id] = res
  return res


def parse_line(line):
    global home

    """Return (aircraft_id, dist_km, alt_m, snr) or None."""

    try:
        m = LINE_RE.search(line)
        if m:
            aircraft_id = m.group(1)
            alt_m       = int(m.group(4))
            snr         = float(m.group(5))
            dist_km     = float(m.group(6))
            flags = m.group(7).strip()
            if snr == None or dist_km > HARD_MAX_KM  or '?' in flags or 'R' in flags:
                return None
            return aircraft_id, dist_km, alt_m, snr

        # TRY APRS line
        m = LINE_RE2.search(line)
        if m:
            aircraft_id = m.group(2)
            alt_m       = int(int(m.group(9)) * 0.3048)
            snr         = float(m.group(10))
            _lat        = int(m.group(3)) + float(m.group(4))/60.0
            _lon        = int(m.group(6)) + float(m.group(7))/60.0
            if m.group(5) == 'S': _lat = -_lat
            if m.group(8) == 'W': _lon = -_lon
            dist_km     = sphere_dist(home, (_lat, _lon))
            if snr == None or dist_km > HARD_MAX_KM:
                return None
            return aircraft_id, dist_km, alt_m, snr

    except:
        return None

    return None


# --------------------------------------------------------------------------- #
# Rolling window
# --------------------------------------------------------------------------- #

class RollingStats:
    """Keeps packets within a time window and computes stats on demand."""

    def __init__(self, window_sec, min_dist_km, test_target = ''):
        self.window_sec  = window_sec
        self.min_dist_km = min_dist_km
        self.packets     = deque()   # (ts, aircraft_id, dist_km, alt_m, snr)
        self.lock        = threading.Lock()
        self.connected   = False
        self.test_target = test_target

    def add(self, aircraft_id, dist_km, alt_m, snr):
        with self.lock:
            self.packets.append((time.monotonic(), aircraft_id, dist_km, alt_m, snr))

    def _evict(self):
        cutoff = time.monotonic() - self.window_sec
        while self.packets and self.packets[0][0] < cutoff:
            self.packets.popleft()

    def stats(self):
        with self.lock:
            self._evict()
            packets = list(self.packets)

        total    = len([(aid, dist, alt, snr) for _, aid, dist, alt, snr in packets
                     if aid != self.test_target])
        far       = [(aid, dist, alt, snr) for _, aid, dist, alt, snr in packets
                     if dist >= self.min_dist_km and aid != self.test_target]
        far_count = len(far)
        avg_snr   = sum(snr for _, _, _, snr in far) / far_count if far_count else 0.0

        test_target_packets =  [(aid, dist, alt, snr) for _, aid, dist, alt, snr in packets
                     if aid == self.test_target]
        test_count = len(test_target_packets)
        test_snr = sum(snr for _, _, _, snr in test_target_packets) / test_count if test_count else 0.0

        # Per-target: total packets in window and packets over threshold
        total_pkts  = {}   # aid -> count of all packets in window
        far_pkts    = {}   # aid -> count of packets over threshold
        for _, aid, dist, alt, snr in packets:
            total_pkts[aid] = total_pkts.get(aid, 0) + 1
        for aid, dist, alt, snr in far:
            far_pkts[aid] = far_pkts.get(aid, 0) + 1

        # Best reception per target: highest distance; average SNR
        best_dist = {}   # aid -> (dist, alt)
        snr_sums  = {}   # aid -> sum of SNR values
        for aid, dist, alt, snr in far:
            if aid not in best_dist or dist > best_dist[aid][0]:
                best_dist[aid] = (dist, alt)
            snr_sums[aid] = snr_sums.get(aid, 0.0) + snr

        # Sort by distance descending
        targets = sorted(
            [(aid, dist, alt,
              snr_sums[aid] / far_pkts.get(aid, 1),
              total_pkts.get(aid, 0), far_pkts.get(aid, 0))
             for aid, (dist, alt) in best_dist.items()],
            key=lambda r: r[1], reverse=True,
        )
        return total, far_count, avg_snr, targets, test_count, test_snr


# --------------------------------------------------------------------------- #
# Display
# --------------------------------------------------------------------------- #

COL_W = 44


def format_elapsed(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def render_column(title, host, port, total, far_count, avg_snr, test_target, test_snr,
                  min_dist_km, window_min, elapsed, connected):
    w = COL_W
    bar = "=" * w
    conn_str = "CONNECTED" if connected else "RECONNECTING..."
    avg_str  = f"{avg_snr:.1f} dB" if far_count else "n/a"
    tavg_str  = f"{test_snr:.1f} dB" if test_target else "n/a"
    lines = [
        bar,
        f"  {title[:w-4]}".ljust(w) if title else " " * w,
        f"  {host}:{port}  [{conn_str}]".ljust(w),
        f"  Window: last {window_min} min | up {elapsed}".ljust(w),
        bar,
        f"  Total packets    : {total}".ljust(w),
        f"  Packets > {min_dist_km:2.0f} km  : {far_count}, avgSNR: {avg_str}".ljust(w),
        f"  Test target      : {test_target}, avgSNR: {tavg_str}".ljust(w),
        bar,
    ]
    return lines


def render_target_table(all_targets, min_dist_km):
    """all_targets: list of (label, targets) per receiver."""
    if not any(t for _, t in all_targets):
        return [f"  No targets > {min_dist_km:.0f} km in window."]

    lines = []
    # Header
    if len(all_targets) == 1:
        lines.append(f" {'ID':<6}       {'Dist':>7} {'Alt':>5}  {'SNR':>6}  {'Pt>th':>5}")
        lines.append(" " + "-" * COL_W)
        for aid, dist, alt, snr, tp, fp in all_targets[0][1]:
            lines.append(f" {aid:<6} {(lookup_ognddb(aid) or '')[:7]:<7} {dist:>5.1f}km {alt:>4}m {snr:>5.1f}dB {fp:>5}")
    else:
        # Two columns: merge targets interleaved by label
        w = COL_W
        hdr = f" {'ID':<6}       {'Dist':>7} {'Alt':>5}  {'SNR':>6}  {'Pt>th':>5}"
        sep = " " + "-" * (w - 2)
        left_lines  = [hdr, sep] + [
            f" {aid:<6} {(lookup_ognddb(aid) or '')[:7]:<7} {dist:>5.1f}km {alt:>4}m {snr:>5.1f}dB {fp:>5}"
            for aid, dist, alt, snr, tp, fp in all_targets[0][1]
        ]
        right_lines = [hdr, sep] + [
            f" {aid:<6} {(lookup_ognddb(aid) or '')[:7]:<7} {dist:>5.1f}km {alt:>4}m {snr:>5.1f}dB {fp:>5}"
            for aid, dist, alt, snr, tp, fp in all_targets[1][1]
        ]
        max_rows = max(len(left_lines), len(right_lines))
        left_lines  += [""] * (max_rows - len(left_lines))
        right_lines += [""] * (max_rows - len(right_lines))
        for l, r in zip(left_lines, right_lines):
            lines.append(f"{l:<{w}}   {r}")
    return lines


def print_display(stat_cols, target_rows):
    os.system("cls" if os.name == "nt" else "clear")
    # Stats boxes
    if len(stat_cols) == 1:
        for line in stat_cols[0]:
            print(line)
    else:
        for a, b in zip(stat_cols[0], stat_cols[1]):
            print(f"{a}   {b}")
    # Target list
    print()
    for line in target_rows:
        print(line)
    print(flush=True)


# --------------------------------------------------------------------------- #
# TCP receiver thread
# --------------------------------------------------------------------------- #

def receiver_thread(host, port, rolling, stop_event):
    while not stop_event.is_set():
        try:
            with socket.create_connection((host, port), timeout=10) as sock:
                rolling.connected = True
                sock.settimeout(2.0)
                buf = ""
                while not stop_event.is_set():
                    try:
                        chunk = sock.recv(4096).decode("utf-8", errors="replace")
                        if not chunk:
                            break
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            result = parse_line(line)
                            if result:
                                rolling.add(*result)
                    except socket.timeout:
                        pass
        except (ConnectionRefusedError, OSError):
            pass
        finally:
            rolling.connected = False
        if not stop_event.is_set():
            time.sleep(5)


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #

def run(receivers, min_dist_km, window_sec, update_interval):
    stop_event = threading.Event()
    for host, port, title, rolling in receivers:
        t = threading.Thread(
            target=receiver_thread,
            args=(host, port, rolling, stop_event),
            daemon=True,
        )
        t.start()

    window_min = window_sec // 60
    start = time.monotonic()

    def redraw():
        now = time.monotonic()
        elapsed = format_elapsed(now - start)
        stat_cols   = []
        all_targets = []
        for host, port, title, rolling in receivers:
            total, far_count, avg_snr, targets, test_target, test_snr = rolling.stats()
            stat_cols.append(render_column(
                title, host, port, total, far_count, avg_snr, test_target, test_snr,
                min_dist_km, window_min, elapsed, rolling.connected,
            ))
            all_targets.append((title, targets))
        target_rows = render_target_table(all_targets, min_dist_km)
        print_display(stat_cols, target_rows)
 
    redraw()
 
    try:
        while True:
            time.sleep(update_interval)
            redraw()

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop_event.set()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Live side-by-side rolling stats from OGN TCP log streams.")
    parser.add_argument("--host",     default="127.0.0.1",
                        help="Host for first receiver (default: 127.0.0.1)")
    parser.add_argument("--port",     type=int, default=50001,
                        help="Port for first receiver (default: 50001)")
    parser.add_argument("--title",    default="",
                        help="Title for first receiver")
    parser.add_argument("--host2",    default="127.0.0.1",
                        help="Host for second receiver (default: 127.0.0.1)")
    parser.add_argument("--port2",    type=int, default=None,
                        help="Port for second receiver (omit for single mode)")
    parser.add_argument("--title2",   default="",
                        help="Title for second receiver")
    parser.add_argument("--window",   type=int, default=1800,
                        help="Rolling window in seconds (default: 1800 = 30 min)")
    parser.add_argument("--dist",     type=float, default=30.0,
                        help="Minimum distance threshold in km (default: 30)")
    parser.add_argument("--target",     default="",
                        help="Test target tracker ID (6 characters)")
    parser.add_argument("--interval", type=int, default=5,
                        help="Console refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    receivers = [(
        args.host, args.port, args.title,
        RollingStats(args.window, args.dist, args.target),
    )]
    if args.port2 is not None:
        receivers.append((
            args.host2, args.port2, args.title2,
            RollingStats(args.window, args.dist, args.target),
        ))

    run(receivers, args.dist, args.window, args.interval)


if __name__ == "__main__":
    main()
