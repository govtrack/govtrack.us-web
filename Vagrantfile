# -*- mode: ruby -*-
# vi: set ft=ruby :


# If you are looking at this script to set up your computer for developing
# the GovTrack website, skip ahead to "START HERE". Thanks!


Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/xenial64"
  config.vm.network "forwarded_port", guest: 8000, host: 8000
  config.vm.provision "shell", inline: <<-SHELL
    # Create a fake manage.py file in ~ so 'vagrant ssh' can find it easily.
    ln -s /vagrant/build/vagrant_manage.py manage.py
    cd /vagrant

    ###############
    # Start here! #
    ###############

    # These instructions are for Ubuntu 16.04. Where the instructions
    # differ for OS X, we'll note those differences.

    # Install system packages
    #########################

    # (Ubuntu only)
    echo Installing system packages...
    sudo apt-get update
    sudo apt install -y -q \
        git python-virtualenv python-lxml python-openid \
        python-oauth2client python-iso8601 python-numpy python-scipy \
        python-prctl python-pip python-xapian

    # On OS X...
    # ----------
    # export CFLAGS=-I/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.10.sdk/usr/include/libxml2
    # pip install virtualenv lxml python-openid python-oauth2 iso-8601 numpy scipy

    # Install Python packages
    #########################

    # If you're following these instructions manually, you should create
    # a "virtualenv" for Python that will hold additional Python packages.
    # With Vagrant, it's not necessary, so it's commented out. But you
    # should run these two commands:
    #
    # virtualenv --system-site-packages .venv
    # source .venv/bin/activate

    # Install Python packages.
    pip install --upgrade -r requirements.txt

    # On OS X, install bcrypt:
    # http://stackoverflow.com/questions/22875270/error-installing-bcrypt-with-pip-on-os-x-cant-find-ffi-h-libffi-is-installed

    # Initialize the database.
    ./manage.py migrate --noinput

    # Load some legislative data
    ############################

    # Get our latest database dump of legislators, committees, and subject areas.
    echo Downloading a partial database dump from GovTrack...
    wget -nc -P /tmp -q http://www.govtrack.us/data/db/django-fixture-{people,committees,billterms}.json

    # And load them.
    echo Loading data...
    ./manage.py loaddata /tmp/django-fixture-people.json
    ./manage.py loaddata /tmp/django-fixture-committees.json
    ./manage.py loaddata /tmp/django-fixture-billterms.json

    # Fetch some data about bills and votes.
    echo Fetching a subset of data files about bills and votes...
    build/rsync.sh
    echo And now am loading it into the database...
    ./parse.py bill --congress=115
    ./parse.py vote --congress=115

    # Update search indexes.
    echo "Initializing search indexes (this part takes a long while)..."
    ./manage.py update_index

  SHELL
end
