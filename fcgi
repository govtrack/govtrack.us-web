#!/bin/bash

# Start, stop, restart, or graceful restart the FastCGI server.
# With no arguments, stops any executing instance and then
# starts a new one. With the argument 'stop', stops all executing
# instances but does not start a new one. With the argument
# 'graceful', a new instance is started on a fresh port and once
# it is started the old instances are killed for a graceful
# restart, using SIGHUP to gracefully end FastCGI.

# change to the site directory, where this script is located
ME=`readlink -m $0`
MYDIR=`dirname $ME`
cd $MYDIR

if [ "$USER" = "" ]; then
	echo "USER environment variable not set.";
	exit;
fi

# Load settings.
PORT=`echo 1000+$UID*2|bc`
if [ -f fcgi.conf ]; then
	. fcgi.conf
fi
if [ "$NAME" = "" ]; then NAME=$PORT; fi
if [ "$INSTANCES" = "" ]; then INSTANCES=6; fi
if [ "$INSTANCES_MIN" = "" ]; then INSTANCES_MIN=$INSTANCES; fi
if [ "$INSTANCES_MAX" = "" ]; then INSTANCES_MAX=$INSTANCES; fi
if [ "$INSTANCE_MAX_REQUESTS" = "" ]; then INSTANCE_MAX_REQUESTS=1000; fi

if [ "$1" = "" ]; then
	# Hard restart: Do a stop first. The rest of this script
	# will start a new instance on the default port.
	./fcgi stop
fi

HOSTNAME=`hostname -I | tr -d ' '` # assumes only one interface
HOSTNAME=127.0.0.1

# Get the CURPID, CURPIDFILE, and CURPORT of the running instance.
for CURPIDFILE in `ls /tmp | egrep "django-fcgi-$NAME(-.*)?.pid"`
do
    CURPID=`cat -- /tmp/$CURPIDFILE`;
    CURPORT=`echo $CURPIDFILE | sed "s/.*-\([0-9]*\).pid/\1/"`;

    # Stop: Kill the running instance (exit after killing all
    # running instances).
    if [ "$1" = "stop" ]; then
        echo "Stopping $CURPORT (pid=$CURPID)...";
        kill -HUP $CURPID;
        
		# Wait for the port to clear.
		CTR=0
		while [ "`netstat -tln |grep $CURPORT`" != "" ]; do
			if [ $CTR -gt 1 ]; then
				echo "Port $CURPORT still bound...";
				netstat -tln |grep $CURPORT;
			fi
			if [ $CTR -gt 10 ]; then
		        echo "Killing $CURPORT (pid=$CURPID)...";
		        kill $CURPID;
				break;
			fi
			CTR=`echo $CTR+1|bc`
			sleep 1;
		done

        rm -f -- /tmp/$CURPIDFILE;
    fi
done

# Stop: Kill the running instance and exit.
if [ "$1" = "stop" ]; then
    exit;
fi

# If it is the same as the running instance's port in a
# graceful restart, add 1.
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

echo "Starting $NAME $HOSTNAME:$PORT x $INSTANCES...";

# select a PIDFILE
PIDFILE=/tmp/django-fcgi-$NAME-$PORT.pid

export NAME=$NAME
PYTHONPATH=.. ./manage.py runfcgi host=$HOSTNAME port=$PORT pidfile=$PIDFILE \
                 workdir=$MYDIR umask=0002 debug=1 \
                 maxchildren=$INSTANCES_MAX minspare=$INSTANCES_MIN maxspare=$INSTANCES_MAX \
                 maxrequests=$INSTANCE_MAX_REQUESTS \
                 timeout=25 \
                 outlog=~/logs/django_output_log errlog=~/logs/django_error_log ;

# Kill the previously running instance.
if [ "$CURPIDFILE" != "" ]; then
    sleep 2; # give the new instance a chance to start up and
             # the old instance a chance to complete requests

    echo "Stopping $CURPIDFILE (port=$CURPORT, pid=$CURPID)...";
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
