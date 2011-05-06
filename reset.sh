#!/bin/sh
mysql -e 'drop database govtrack'
mysql -e 'create database govtrack charset utf8'
rm -f database.sqlite
./manage.py syncdb --noinput --migrate
./generate.py

mkdir -p log

if [ "$1" = "parse" ]; then
    ./parse.py person
    ./parse.py committee
    ./parse.py vote --congress=112
    ./parse.py bill --congress=112
fi

if [ "$1" = "quick-parse" ]; then
    ./parse.py person --disable-events
    ./parse.py committee --disable-events
    ./parse.py vote --disable-events --congress=112
    ./parse.py bill --disable-events --congress=112
fi
