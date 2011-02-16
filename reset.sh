#!/bin/sh
mysql -e 'drop database govtrack'
mysql -e 'create database govtrack charset utf8'
rm -f database.sqlite
./manage.py syncdb --noinput --migrate
./generate.py

if [ "$1" = "parse" ]; then
    ./parse.py person
    ./parse.py committee
fi
