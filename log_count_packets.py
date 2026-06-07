#!/usr/bin/python
#  process ogn-decode output, count received packets
import re
import sys
import argparse

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
    .*
    (\s\s[?\s!R*]{4}\s\s)                  # optional flags: !, ?, R (4)
    """,
    re.VERBOSE,
)


LINE_RE2 = re.compile(
    r"""
    APRS\s<-\s(\w+)                             # aircraft ID (1)
    >(OG\w{3,4})                                # dstcall (2)
    (.*:).                                      # relay info here (3) - it is ok if packet is relayed
    (\d{6})h                                    # time (4)
    """,
    re.VERBOSE,
)

def parse_log(path, test_target):
    global home

    dvs_c = 0
    records_c = 0
    target_c = 0

    prev_time = -1

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()

            m = LINE_RE.search(line)
            if m:
                if m.group(4) != None and 'R' in m.group(4):
                    continue
                if '  ?  ' in line or m.group(4) != None and '?' in m.group(4):
                    continue

                if m.group(3) is not None:
                    prev_time = m.group(3)

                if m.group(1) == test_target:
                    target_c += 1

                records_c += 1
                continue

            m = LINE_RE2.search(line)
            if m:
                if m.group(2) == 'OGNDVS':
                    dvs_c += 1
                    records_c += 1
                    continue

                if m.group(2) not in ('OGNTRK', 'OGADSL', 'OGNFNT', 'OGFLR7', 'OGPAW', 'OGMSHT'):
                    continue

                if m.group(4) is not None and m.group(4) == prev_time and m.group(2) not in ('OGMSHT'):
                    continue

                if m.group(1)[3:] == test_target and 'RELAY' not in m.group(3):
                    target_c += 1

                records_c += 1
                continue

    return (target_c, records_c, dvs_c)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser( description="Bin OGN log packets into time windows and output CSV.")
    parser.add_argument("log", help="Path to log file")
    parser.add_argument("--target", default='A1B2C3',
                        help="Test target (default: A1B2C3)")

    args = parser.parse_args()

    target, records, dvs = parse_log(args.log,args.target)
    print("%d" % target)
    print("%d" % records)
    print("%d" % dvs)

if __name__ == "__main__":
    main()
