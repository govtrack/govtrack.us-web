#!/bin/sh
mysql -e 'drop database govtrack'
mysql -e 'create database govtrack charset utf8'
./manage.py syncdb --noinput --migrate
./generate.py
