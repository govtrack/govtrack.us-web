#!/bin/bash

# Start, graceful switch, or stop the FastCGI Python instance.
# Run with the argument 'stop' to stop all executing instances.
# Otherwise, a new instance is started on a fresh port and once
# it is started the old instances are killed for a graceful
# restart, using SIGHUP to gracefully end FastCGI.

# change to the site directory, where this script is located
ME=`readlink -m $0`
MYDIR=`dirname $ME`
cd $MYDIR

HOSTNAME=`hostname -I | tr -d ' '` # assumes only one interface
HOSTNAME=127.0.0.1

# Get the CURPID, CURPIDFILE, and CURPORT of the running instance.
for CURPIDFILE in `ls /tmp | egrep "django-fcgi-$USER(-.*)?.pid"`
do
    CURPID=`cat -- /tmp/$CURPIDFILE`;
    CURPORT=`echo $CURPIDFILE | sed "s/django-fcgi-$USER-\([0-9]*\).pid/\1/"`;

    # Stop: Kill the running instance and exit.
    if [ "$1" = "stop" ]; then
        echo "Stopping $CURPORT (pid=$CURPID)...";
        kill -HUP $CURPID;
        rm -f -- /tmp/$CURPIDFILE;
    fi
done

# Stop: Kill the running instance and exit.
if [ "$1" = "stop" ]; then
    exit;
fi

# Select a port for the new instance.
PORT=`echo 1000+$UID*2|bc`

# If it is the same as the running instance's port, add 1.
if [ "$PORT" = "$CURPORT" ]; then
    PORT=`echo $PORT+1|bc`
fi

# Start the new instance...

# Wait for the port to clear.
CTR=0
while [ "`netstat -tln |grep $PORT`" != "" ]; do
	if [ $CTR -gt 1 ]; then
		echo "Port $PORT already bound...";
		netstat -tln |grep $PORT;
	fi
	CTR=`echo $CTR+1|bc`
	sleep 1;
done

INSTANCES=8

echo "Starting $HOSTNAME:$PORT x $INSTANCES...";

# select a PIDFILE
PIDFILE=/tmp/django-fcgi-$USER-$PORT.pid

PYTHONPATH=.. ./manage.py runfcgi host=$HOSTNAME port=$PORT pidfile=$PIDFILE \
                 workdir=$MYDIR umask=0002 debug=1 \
                 maxchildren=$INSTANCES maxspare=$INSTANCES \
                 outlog=~/logs/django_output_log errlog=~/logs/django_error_log ;

# Kill the previously running instance.
if [ "$CURPIDFILE" != "" ]; then
    sleep 2; # give the new instance a chance to start up and
             # the old instance a chance to complete requests

    echo "Stopping $CURPORT (pid=$CURPID)...";
    kill -HUP $CURPID;
    rm -f -- /tmp/$CURPIDFILE;

    # wait for the port to clear
    CTR=0
    while [ "`netstat -tln |grep $CURPORT`" != "" ]; do
	if [ $CTR -gt 1 ]; then
		echo "Waiting for port $CURPORT to be freed...";
		netstat -tln |grep $PORT;
	fi
	CTR=`echo $CTR+1|bc`
	sleep 1;
    done
fi
