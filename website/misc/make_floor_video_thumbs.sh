#!/bin/bash

# Run from the web source directory.

rm -f /tmp/00000001.jpg
nohup mplayer -really-quiet -noconsolecontrols -nosound -vo jpeg:outdir=/tmp -frames 1 -nocache mmsh://grani-senateenc01.wm.llnwd.net/grani_senateenc01 > /dev/null 2&>/dev/null
mv /tmp/00000001.jpg static/images/floor_thumb_senate.jpeg

rm -f /tmp/00000001.jpg
nohup mplayer -really-quiet -noconsolecontrols -nosound -vo jpeg:outdir=/tmp -frames 1 -nocache mmsh://grani-househ264enc01.wm.llnwd.net/grani_houseH264ENC01 > /dev/null 2&>/dev/null
mv /tmp/00000001.jpg static/images/floor_thumb_house.jpeg


