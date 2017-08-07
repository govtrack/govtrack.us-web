#!/bin/bash
cd /vagrant
export DEBUG=1
if [ -f local/settings.env ]; then
	echo "using local/settings.env"
	set -o allexport
	source local/settings.env; 
fi
./manage.py "$@"
