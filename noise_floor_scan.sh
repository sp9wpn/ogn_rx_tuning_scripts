#!/bin/bash
# Measure 868MHz noise floor across input gains
# for best results, SDR should be terminated with 50 Ohm standard
DEV=${1:-0}

rm /tmp/rtl$DEV.log

for g in 0.0 0.9 1.4 2.7 3.7 7.7 8.7 12.5 14.4 15.7 16.6 19.7 20.7 22.9 25.4 28.0 29.7 \
32.8 33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6 ; do
  echo -n "$g, " >> /tmp/rtl$DEV.log
  rtl_power -d $DEV -f 867000K:869000K:2000k -i 15s -1 -g $g >> /tmp/rtl$DEV.log
  sleep 1
done

cat /tmp/rtl$DEV.log
