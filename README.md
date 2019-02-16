GovTrack website frontend
=========================

This repo contains the source code of the front-end for www.GovTrack.us.
The data-gathering scripts are elsewhere.

Local Development
-----------------

### Development using Vagrant

GovTrack.us is based on Python 3 and Django 1.x and runs on Ubuntu 16.04 or OS X. To simplify local development, we have a `Vagrantfile` in this directory. You can get started quickly simply by installing [Vagrant](https://www.vagrantup.com/) and running:

    # Get this repo (you must clone with `--recursive`)
    git clone --recursive https://github.com/govtrack/govtrack.us-web.git

    # Change to this repo's directory.
    cd govtrack.us-web

    # Start Vagrant.
    vagrant up

    # Create your initial user.
    vagrant ssh -- -t ./manage.py createsuperuser

    # Start debug server.
    vagrant ssh -- -t ./manage.py runserver 0.0.0.0:8000

    # Visit the website in your browser at http://localhost:8000!

    # Stop the virtual machine when you are done.
    vagrant suspend

    # Destroy the virtual machine when you no longer are working on GovTrack ever again (or when you want your disk space back).
    vagrant destroy

Even though the site is running in the virtual machine, it is using the source files on your host computer. So you can open up the files that you got from this repository in your favorite text editor like normal and the virtual machine will see your changes. When you edit .py files, `runserver` will automatically restart to re-load the code. The site's database and search indexes are also stored on the host machine so they will be saved even when you `destroy` your vagrant box.

See further down about configuration.

### Development without Vagrant

To set up GovTrack development without a virtual machine, get the source code in this repository (use `--recursive`, as mentioned above), and then you'll need to follow along with the steps in our [Vagrantfile](Vagrantfile) by just looking at what we did and doing the same on your command line.

At the end:

    # Create your initial user.
    ./manage.py createsuperuser

    # Start the debug server.
    ./manage.py runserver

### Configuration

Some features of the site require additional configuration. To set configuration variables, create a file named `local/settings.env` and set any of the following optional variables (defaults are shown where applicable):

    # Database server.
    # See https://github.com/kennethreitz/dj-database-url
    DATABASE_URL=sqlite:///local/database.sqlite...

    # Memcached server.
    # See https://github.com/ghickman/django-cache-url#supported-caches
    CACHE_URL=locmem://opendataiscool

    # Search server.
    # See https://github.com/simpleenergy/dj-haystack-url#url-schema
    #
    # For local development you may want to use the (default) Xapian search engine, e.g.:
    # xapian:/home/username/govtrack.us-web/xapian_index_person
    # You'll need to `apt-get install python-xapian` and `pip install xapian-haystack`
    # or see https://github.com/notanumber/xapian-haystack.
    #
    # For a production deployment you may want to use Solr instead, e.g.:
    # solr:http://localhost:8983/solr/person
    #
    # You can also specify 'simple' to have a dummy search backend that
    # does not actually index or search anything.
    HAYSTACK_PERSON_CONNECTION=xapian:local/xapian_index_person
    HAYSTACK_BILL_CONNECTION=xapian:local/xapian_index_bill

    # Django uses a secret key to provide cryptographic signing. It should be random
    # and kept secure. You can generate a key with `./manage.py generate_secret_key`
    SECRET_KEY=(randomly generated on each run if not specified)

See `settings.env.template` for details, especially for values used in production.

Additionally, some data files are stored in separate repositories and must be obtained and the path configured in settings.env:

* congress project bill status data (etc.)
* congress-legislators data
* legislator photos (symlink photos directory to static/legislator-photos)
* GovTrack's scorecards, miscondut, and name pronuciation repositories

# Credits

Emoji icons by http://emojione.com/developers/.

# Production Deployment Notes

On my Ubuntu 14.04 box I had to:

    pip install --upgrade pip setuptools six

To set up a MySQL database you'll need the OS MySQL package and the Python package:

    apt-get install libmysqlclient-dev
    pip install mysqlclient

To use memcached:

    pip install pylibmc
