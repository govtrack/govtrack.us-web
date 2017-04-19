#!/usr/bin/env bash

# NOTE: This script needs to run with superuser (sudo) permissions.

set -ex

GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

cd $GOVTRACK_ROOT

# Set up a System-D service
honcho run build/render_template.py conf/systemd-service.template \
    > /etc/systemd/system/govtrack.service

# Use the Nginx configuration with SSL enabled
honcho run build/render_template.py conf/nginx.conf.template \
    > /etc/nginx/sites-available/govtrack
cp conf/nginx-ssl.conf /etc/ssl/
ln --force --symbolic /etc/nginx/sites-available/govtrack \
                      /etc/nginx/sites-enabled/govtrack

# Create folders for govtrack runtime data
mkdir -p /var/cache/govtrack/
mkdir -p /var/log/govtrack/
mkdir -p /var/lock/govtrack/
chmod 777 /var/lock/govtrack

nginx -t
