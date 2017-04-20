#!/usr/bin/env bash

set -ex

GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

if [ "$S3_BACKUP_BUCKET" = "" ]
then
  echo "You must set an S3_BACKUP_BUCKET environment variable."
  exit 1
fi

mkdir -fp ~/.aws
honcho run \
  $GOVTRACK_ROOT/build/render_template.py $GOVTRACK_ROOT/conf/aws.credentials.template
  > ~/.aws/credentials

honcho run \
  aws sync data s3://$S3_BACKUP_BUCKET