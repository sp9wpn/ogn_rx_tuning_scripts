#!/usr/bin/env python3
"""
ogn-rf gain control.
Usage: python adjust_gain.py <host> <port> <gain>
"""

import socket
import sys
import re

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parse_gain(data: str) -> float | None:
    """Extract gain value from a line like 'RF.OGN.Gain=12.2 dB'"""
    match = re.search(r'RF\.OGN\.Gain=([\d.]+)\s*dB', data)
    if match:
        return float(match.group(1))

    match = re.search(r'Stepped\s*OGN\.Gain\s*to\s*([\d.]+)\s*dB', data)
    if match:
        return float(match.group(1))

    match = re.search(r'BkgNoise\s*=\s*[-\d.]+dB,\s*Gain\s*=\s*([\d.]+)dB\s*', data)
    if match:
        return float(match.group(1))

    return None


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <host> <port> <gain>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    target_gain = float(sys.argv[3])

    eprint(f"adjust_gain.py: connecting to {host}:{port}, target gain: {target_gain} dB")

    with socket.create_connection((host, port)) as sock:
        f = sock.makefile('rb')

        # Send initial newline to trigger parameter report
        sock.sendall(b'\n')

        minmaxSet = 0

        while True:
            line = f.readline()
            if not line:
                eprint("Connection closed by remote.")
                print("error")
                sys.exit(1)

            line = line.decode('utf-8', errors='replace').strip()
            if not line:
                continue

            current_gain = parse_gain(line)

            if current_gain is None:
                continue  # Not the gain line, keep reading

            if minmaxSet == 0:
                if current_gain == target_gain:
                    eprint("Target gain already set.")
                    print(f"{current_gain}")
                    sys.exit(0)

                if current_gain < target_gain:
                    cmd1 = "RF.OGN.MinNoise=45"
                    cmd2 = "RF.OGN.MaxNoise=50"
                    minmaxSet = 1
                else:
                    cmd1 = "RF.OGN.MinNoise=-20"
                    cmd2 = "RF.OGN.MaxNoise=-15"
                    minmaxSet = -1

                sock.sendall((cmd1 + '\n').encode())
                sock.sendall((cmd2 + '\n').encode())


            if minmaxSet != 0:
                if ( (minmaxSet == 1 and current_gain >= target_gain) or
                         (minmaxSet == -1 and current_gain <= target_gain) ):
                    cmd1 = "RF.OGN.MinNoise=-20"
                    cmd2 = "RF.OGN.MaxNoise=50"
                    sock.sendall((cmd1 + '\n').encode())
                    sock.sendall((cmd2 + '\n').encode())
                    eprint(f"Gain {current_gain} set.")
                    print(f"{current_gain}")
                    sys.exit(0)
                    break


if __name__ == '__main__':
    main()
