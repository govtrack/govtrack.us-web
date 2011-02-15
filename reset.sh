#!/bin/sh
mysql -e 'drop database govtrack'
mysql -e 'create database govtrack charset utf8'
rm -f database.sqlite
./manage.py syncdb --noinput --migrate
./generate.py
