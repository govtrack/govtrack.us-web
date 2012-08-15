#!/bin/bash

# Run from the web source directory.

mkdir -p static/images/dynamic

rm -f /tmp/00000001.jpg
nohup mplayer -really-quiet -noconsolecontrols -nosound -vo jpeg:outdir=/tmp -frames 1 -nocache mmsh://grani-senateenc01.wm.llnwd.net/grani_senateenc01 > /dev/null 2&>/dev/null
if [ -e /tmp/00000001.jpg ]; then mv /tmp/00000001.jpg static/images/dynamic/floor_thumb_senate.jpeg; fi

rm -f /tmp/00000001.jpg
nohup mplayer -really-quiet -noconsolecontrols -nosound -vo jpeg:outdir=/tmp -frames 1 -nocache mmsh://grani-househ264enc01.wm.llnwd.net/grani_houseH264ENC01 > /dev/null 2&>/dev/null
if [ -e /tmp/00000001.jpg ]; then mv /tmp/00000001.jpg static/images/dynamic/floor_thumb_house.jpeg; fi


