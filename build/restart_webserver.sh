#!/usr/bin/env bash

# NOTE: This script needs to run with superuser (sudo) permissions.

set -ex

systemctl daemon-reload
systemctl restart govtrack
systemctl restart nginx
