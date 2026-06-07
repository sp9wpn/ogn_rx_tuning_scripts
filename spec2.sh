#!/usr/bin/bash
#   save two ogn-rf spectrograms to a image, annotate with gain setting

cd /tmp
name1=${1:-sdr1}
name2=${2:-sdr2}
rx1_port=${3:-127.0.0.1:8080}
rx2_port=${4:-127.0.0.1:8090}

wget -O /tmp/rx1.png -o /dev/null http://$rx1_port/spectrogram.png &
pid1=$!
wget -O /tmp/rx2.png -o /dev/null http://$rx2_port/spectrogram.png &
pid2=$!

wait $pid1 $pid2

wget -O /tmp/.noise_scan.html -o /dev/null http://$rx1_port/
gain_rx1=`grep "<tr><td>RF.OGN.Gain</td>" < /tmp/.noise_scan.html | sed -r -e 's#<tr><td>RF.OGN.Gain</td><td align=right><b>\\[[0-9]+\\] ##' -e 's# dB</b></td></tr>##'`
wget -O /tmp/.noise_scan.html -o /dev/null http://$rx2_port/
gain_rx2=`grep "<tr><td>RF.OGN.Gain</td>" < /tmp/.noise_scan.html | sed -r -e 's#<tr><td>RF.OGN.Gain</td><td align=right><b>\\[[0-9]+\\] ##' -e 's# dB</b></td></tr>##'`

# to fix synchronization errors: change 1024x800 to eg. 1024x800+0+160

gm convert -crop 1024x800 -pointsize 50 -fill yellow -font /usr/share/fonts/X11/Type1/NimbusSans-Bold.pfb -draw "text 40,80 $name1" -pointsize 30 -draw "text 40,750 'gain $gain_rx1'" -strokewidth 5 -stroke orange -draw "line 1023,0,1023,799" /tmp/rx1.png /tmp/rx1.tmp.png

gm convert -crop 1024x800 -pointsize 50 -fill yellow -font /usr/share/fonts/X11/Type1/NimbusSans-Bold.pfb -draw "text 40,80 $name2" -pointsize 30 -draw "text 40,750 'gain $gain_rx2'" /tmp/rx2.png /tmp/rx2.tmp.png

gm convert /tmp/rx1.tmp.png /tmp/rx2.tmp.png +append /tmp/spec_`date +%d%m%Y-%H%M%S`_${gain_rx1}.png

rm /tmp/.noise_scan.html /tmp/rx1.png /tmp/rx2.png /tmp/rx1.tmp.png /tmp/rx2.tmp.png
