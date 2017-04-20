#!/usr/bin/env bash

# NOTE: This script needs to run with superuser (sudo) permissions.

set -ex

GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

cd $GOVTRACK_ROOT

# Install the cron-table based on the template
honcho run build/render_template.py conf/crontab.template | crontab -
