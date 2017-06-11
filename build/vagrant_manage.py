#!/bin/bash
cd /vagrant
source .env/bin/activate
export DEBUG=1
./manage.py "$@"
