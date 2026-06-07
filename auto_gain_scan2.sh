#!/usr/bin/bash
#   cycle input gains on two SDRs and dump ogn_decode outputs
#   count received packets


## Possible gains:
#  0.0 0.9 1.4 2.7 3.7 7.7 8.7 12.5 14.4 15.7 16.6 19.7 20.7 22.9 25.4 28.0 29.7 32.8 33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6

#rx1
GAINS1=${GAINS1:-33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6}
#rx2
GAINS2=${GAINS2:-33.8 36.4 37.2 38.6 40.2 42.1 43.4 43.9 44.5 48.0 49.6}

devname1=${DEVNAME1:-sdr1}
devname2=${DEVNAME2:-sdr2}

TIME=${TIME:-90}

rtl1="localhost"
rtl1_rf="50000"
rtl1_decode="50001"
rtl1_web="8080"

rtl2="localhost"
rtl2_rf="50100"
rtl2_decode="50101"
rtl2_web="8090"


LOG1=/tmp/.gain_scan.${devname1}.log
LOG2=/tmp/.gain_scan.${devname2}.log
OUTPUT1=/tmp/auto_gain_scan.${devname1}.log
OUTPUT2=/tmp/auto_gain_scan.${devname2}.log

echo "RF.OGN.MinNoise=-20" > /dev/tcp/$rtl1/$rtl1_rf
echo "RF.OGN.MaxNoise=50" > /dev/tcp/$rtl1/$rtl1_rf

echo "RF.OGN.MinNoise=-20" > /dev/tcp/$rtl2/$rtl2_rf
echo "RF.OGN.MaxNoise=50" > /dev/tcp/$rtl2/$rtl2_rf

sleep 1

read -ra glist1 <<< "$GAINS1"
read -ra glist2 <<< "$GAINS2"

i=0; j=0

while true ; do
    ./adjust_gain.py $rtl1 $rtl1_rf ${glist1[i]} >/tmp/.auto_gain_1 2>/dev/null &
    pid1=$! 
    ./adjust_gain.py $rtl2 $rtl2_rf ${glist2[j]} >/tmp/.auto_gain_2 2>/dev/null &
    pid2=$!

    wait $pid1 $pid2

    g1=`cat /tmp/.auto_gain_1`
    g2=`cat /tmp/.auto_gain_2`

    ( nc $rtl1 $rtl1_decode >$LOG1 2>/dev/null) &
    ( nc $rtl2 $rtl2_decode >$LOG2 2>/dev/null) &

    sleep $TIME

    # uncomment to fetch spectrograms with each change
    # ./spec2.sh $devname1 $devname2 $rtl1:$rtl1_web $rtl2:$rtl2_web

    killall nc

    count1=`./log_count_packets.py $LOG1`
    c_target1=`echo "$count1" | head -1`
    c_total1=`echo "$count1" | head -2 | tail -1`
    c_dvs1=`echo "$count1" | tail -1`

    count2=`./log_count_packets.py $LOG2`
    c_target2=`echo "$count2" | head -1`
    c_total2=`echo "$count2" | head -2 | tail -1`
    c_dvs2=`echo "$count2" | tail -1`

    echo "`date +'%Y%m%d-%H%M%S'`;$devname1;$g1;$c_target1;$c_total1;$c_dvs1;$TIME" >> $OUTPUT1
    echo "`date +'%Y%m%d-%H%M%S'`;$devname2;$g2;$c_target2;$c_total2;$c_dvs2;$TIME" >> $OUTPUT2

    echo -n "`date +'%H:%M:%S'` $devname1 $g1 Trg: $c_target1  Total: $c_total1  DVS:$c_dvs1"
    echo "      $devname2 $g2 Trg: $c_target2  Total: $c_total2  DVS:$c_dvs2"

    sleep 1

    ((i = (i + 1) % ${#glist1[@]}))
    ((j = (j + 1) % ${#glist2[@]}))

    if [ $i == 0 ] ; then echo "#---" >> $OUTPUT1 ; fi
    if [ $j == 0 ] ; then echo "#---" >> $OUTPUT2 ; fi
done
