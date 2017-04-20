#!/usr/bin/env bash

# NOTE: This script needs to run with superuser (sudo) permissions.

set -ex

GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

mkdir -p /etc/ssl/local/acme-wk-public
openssl dhparam -outform pem -out /etc/ssl/local/dhparam2048.pem 2048

# Build a command to request an SSL certificate using certbot.
certbot_command=$(honcho run python <<EOF

from __future__ import print_function
import os

# Get a comma-separated list of domains from the environment.
try:
    os.environ['SSL_HOSTS']
except KeyError:
    raise KeyError('You must specify SSL_HOSTS in an environment variable.')

# Start building the command.
cmd = ('certbot certonly'
       ' --webroot'
       ' -w /etc/ssl/local/acme-wk-public')

# Add each of the domains from the environment variable.
for host in hosts.split(','):
    cmd += ' -d ' + host.strip()

# Send the list of domains to stdout.
print(cmd)

EOF
)

exec(certbot_command)
