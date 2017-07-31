#!/bin/bash
cd /vagrant
export DEBUG=1
if [ -f settings.env ]; then
	echo "using settings.env"
	set -o allexport
	source settings.env; 
fi
./manage.py "$@"
