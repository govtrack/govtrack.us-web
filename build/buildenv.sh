#!/bin/sh
ENV=.env

echo Creating virtual environment
virtualenv $ENV

echo Install PIP inside virtual environment
$ENV/bin/easy_install pip

echo Installing dependencies to virtual environment
$ENV/bin/pip install --upgrade -r ./build/pipreq.txt
