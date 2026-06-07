#!/usr/bin/bash
# cycle input gains and dump ogn_decode output, count received packets at distances

## Possible gains:
#  0.0 0.9 1.4 2.7 3.7 7.7 8.7 12.5 14.4 15.7 16.6 19.7 20.7 22.9 25.4 28.0 29.7 32.8 33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6

GAINS1=${GAINS1:-20.7 22.9 25.4 28.0 29.7 32.8 33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6}

devname1=${DEVNAME1:-sdr1}

TIME=${TIME:-71}

rtl1="localhost"
rtl1_rf="50000"
rtl1_decode="50001"
rtl1_web="8080"

LOG1=/tmp/.gain_scan_dx.${devname1}.log
OUTPUT1=/tmp/auto_gain_scan_dx.${devname1}.log

echo "RF.OGN.MinNoise=-20" > /dev/tcp/$rtl1/$rtl1_rf
echo "RF.OGN.MaxNoise=50" > /dev/tcp/$rtl1/$rtl1_rf

sleep 1

read -ra glist1 <<< "$GAINS1"

i=0;

while true ; do
    ./adjust_gain.py $rtl1 $rtl1_rf ${glist1[i]} >/tmp/.auto_gain_1 2>/dev/null &
    pid1=$! 

    wait $pid1

    g1=`cat /tmp/.auto_gain_1`

    ( nc $rtl1 $rtl1_decode >$LOG1 2>/dev/null) &

    sleep $TIME

    # uncomment to fetch spectrogram
    # ./spec1.sh $devname1 $rtl1:$rtl1_web

    killall nc

    count1=`~pi/auto_gain_scan/log_count_packets_dx.py $LOG1 2>/dev/null`
    c_total=`echo "$count1" | head -1`
    c_dx1=`echo "$count1" | head -2 | tail -1`
    c_dx2=`echo "$count1" | head -3 | tail -1`
    c_dx3=`echo "$count1" | head -4 | tail -1`
    c_dx4=`echo "$count1" | tail -1`

    echo "`date +'%Y%m%d-%H%M%S'`;$devname1;$g1;$c_total;$c_dx1;$c_dx2;$c_dx3;$c_dx4;$TIME" >> $OUTPUT1

    echo "`date +'%H:%M:%S'` $devname1 $g1 total: $c_total  DX: $c_dx1  $c_dx2  $c_dx3  $c_dx4"

    sleep 1

    ((i = (i + 1) % ${#glist1[@]}))

    if [ $i == 0 ] ; then echo "#---" >> $OUTPUT1 ; fi
done
