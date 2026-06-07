#!/usr/bin/python
#  process ogn-decode output, count received packets at 4 distances
import re
import sys
import argparse
import math

home = (50.27286, 18.67223)
DX1_KM = 30 
DX2_KM = 50 
DX3_KM = 70 
DX4_KM = 90 


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

LINE_RE = re.compile(
    r"""
    [\d.]+sec:                             # timing
    [\d.]+MHz:\s+                          # frequency
    .*
    [\d:]+:(\w+)\s+                        # protocol:address (1)
    (([\d]{6}):\s)?                        # time (3)
    \[\s*([+-][\d.]+),\s*([+-][\d.]+)\]deg # lat, lon (4, 5)
    .*?
    ([\d.]+)/[\d.]+dB                      # SNR / noise — comes before km (6)
    .*?
    ([\d.]+)km\s+[\d.]+deg                 # distance km (7)
    \s+[+-][\d.]+deg                       # elevation angle
    (\s\s[?\s!R*]{4}\s\s)                  # optional flags: !, ?, R (8)
    """,
    re.VERBOSE,
)


LINE_RE2 = re.compile(
    r"""
    APRS\s<-\s(\w+)                        # aircraft ID (1)
    >(OG\w{3,4})                           # dstcall (2)
    (.*)                                   # relay info here (3)
    ,qOR:.
    (\d{6})h                               # time (4)
    (\d{2})([\d.]+)(N|S).                  # latitude (5, 6, 7)
    (\d{3})([\d.]+)(E|W).      	           # longitude (8, 9, 10)
    """,
    re.VERBOSE,
)


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


def parse_log(path):
    global home

    dx1_c = 0
    dx2_c = 0
    dx3_c = 0
    dx4_c = 0
    records_c = 0

    prev_time = -1

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()

            m = LINE_RE.search(line)
            if m:
                if m.group(8) != None and 'R' in m.group(8):
                    continue
                if '  ?  ' in line or m.group(8) != None and '?' in m.group(8):
                    continue

                if m.group(3) is not None:
                    prev_time = m.group(3)

                if m.group(7) == None:
                    continue

                dist_km = float(m.group(7))
                if dist_km >= 300:
                    continue
                if dist_km >= DX1_KM:
                  dx1_c += 1
                  print (dist_km, line, file=sys.stderr)
                if dist_km >= DX2_KM: dx2_c += 1
                if dist_km >= DX3_KM: dx3_c += 1
                if dist_km >= DX4_KM: dx4_c += 1

                records_c += 1
                continue

            m = LINE_RE2.search(line)
            if m:
                if m.group(2) not in ('OGNTRK', 'OGADSL', 'OGNFNT', 'OGFLR7', 'OGPAW'):
                    continue

                if m.group(4) is not None and m.group(4) == prev_time and m.group(2) not in ('OGMSHT'):
                    continue

                if m.group(3) != '':                    # relay
                    continue

                _lat        = int(m.group(5)) + float(m.group(6))/60.0
                _lon        = int(m.group(8)) + float(m.group(9))/60.0
                if m.group(7) == 'S': _lat = -_lat
                if m.group(10) == 'W': _lon = -_lon

                dist_km     = sphere_dist(home, (_lat, _lon))
                if dist_km >= 300:
                    continue
                if dist_km >= DX1_KM:
                  dx1_c += 1
                  print (dist_km, line, file=sys.stderr)
                if dist_km >= DX2_KM: dx2_c += 1
                if dist_km >= DX3_KM: dx3_c += 1
                if dist_km >= DX4_KM: dx4_c += 1

                records_c += 1
                continue

    return (records_c, dx1_c, dx2_c, dx3_c, dx4_c)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser( description="Bin OGN log packets into distance windows and output CSV.")
    parser.add_argument("log", help="Path to log file")

    args = parser.parse_args()

    records, dx1, dx2, dx3, dx4 = parse_log(args.log)
    print("%d" % records)
    print("%d" % dx1)
    print("%d" % dx2)
    print("%d" % dx3)
    print("%d" % dx4)

if __name__ == "__main__":
    main()
