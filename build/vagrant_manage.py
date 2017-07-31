#!/bin/bash
cd /vagrant
export DEBUG=1
./manage.py "$@"
