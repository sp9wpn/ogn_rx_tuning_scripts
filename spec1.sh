#!/usr/bin/bash
# save ogn-rf spectrogram to a file, annotate with noise and gain setting
cd /tmp
name1=${1:-sdr1}
rx1_port=${2:-127.0.0.1:8080}

wget -O /tmp/rx1.png -o /dev/null http://$rx1_port/spectrogram.png &
pid1=$!

wait $pid1

wget -O /tmp/.noise_scan.html -o /dev/null http://$rx1_port/
gain_rx1=`grep "<tr><td>RF.OGN.Gain</td>" < /tmp/.noise_scan.html | 
 sed -r -e 's#<tr><td>RF.OGN.Gain</td><td align=right><b>\\[[0-9]+\\] ##' -e 's# dB</b></td></tr>##'`
noise_rx1=`grep "<tr><td>Measured noise</td>" < /tmp/.noise_scan.html | 
 sed -e 's#<tr><td>Measured noise</td><td align=right><b>##'  -e 's# dB</b></td></tr>##'`

gm convert -crop 1024x800 -pointsize 50 -fill yellow -font /usr/share/fonts/X11/Type1/NimbusSans-Bold.pfb \
-draw "text 40,80 $name1" -pointsize 30 -draw "text 40,710 'gain: $gain_rx1'" -draw "text 40,750 'noise: $noise_rx1'" \
/tmp/rx1.png /tmp/rx1.tmp.png

mv /tmp/rx1.tmp.png /tmp/spec_`date +%Y%m%d-%H%M%S`_${gain_rx1}.png

rm /tmp/.noise_scan.html /tmp/rx1.png 
