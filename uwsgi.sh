#!/bin/bash

# Start, stop, reload, or restart the uwsgi server.
# With no arguments, stops any executing instance and then
# starts a new one. With the argument 'stop', stops all executing
# instances but does not start a new one. With 'reload', sends
# a HUP to ask uwsgi to gracefully reload, or starts a
# new process if one isn't running.

# change to the site directory, where this script is located
ME=`readlink -m $0`
MYDIR=`dirname $ME`
cd $MYDIR

if [ "$USER" = "" ]; then
	echo "USER environment variable not set.";
	exit;
fi

if [ "$1" = "" ]; then
	# Hard restart: Do a stop first. The rest of this script
	# will start a new instance on the default port.
	$ME stop
fi

# Load configuration.
source uwsgi.conf
pidfile=/tmp/uwsgi_govtrack_$NAME.pid

# Stop a running process.
if [[ "$1" = "stop" && -e $pidfile ]]; then
	echo "Stopping..."
	pid=$(cat $pidfile)
    kill -QUIT $pid
	
	# Wait till it actually exists.
	while kill -0 $pid 2> /dev/null;
	do
		sleep 1
		echo Waiting...
	done

	rm $pidfile
fi

# Kick a running process to reload.
if [[ "$1" = "reload" && -e $pidfile ]]; then
	pid=$(cat $pidfile)
	if kill -HUP $pid; then
		echo Reload signal sent.
		exit
	fi
	# Process doesn't seem to be running, so continue and start one.
fi

# Stop: Kill the running instance and exit.
if [ "$1" = "stop" ]; then
    exit;
fi

# Start the new instance...

echo "Starting..."

# daemonize if DEBUG is not set
if [ -z "$DEBUG" ]; then
	daemonize="--daemonize /dev/null --pidfile $pidfile --processes $PROCESSES --cheaper 2"
fi

.env/bin/uwsgi $daemonize --socket /tmp/uwsgi_govtrack_$NAME.sock --chmod-socket=666 --wsgi-file wsgi.py
