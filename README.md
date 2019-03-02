GovTrack website frontend
=========================

This repo contains the source code of the front-end for www.GovTrack.us.
The data-gathering scripts are elsewhere.

Local Development
-----------------

### Development using Vagrant

GovTrack.us is based on Python 3 and Django 2.1 and runs on Ubuntu 18.04 or OS X. To simplify local development, we have a `Vagrantfile` in this directory. You can get started quickly simply by installing [Vagrant](https://www.vagrantup.com/) and running:

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
* legislator photos (static/legislator-photos is symlinked to ../data/legislators-photos/photos, so this must go in `data` for now)
* GovTrack's scorecards, miscondut, and name pronuciation repositories

# Credits

Emoji icons by http://emojione.com/developers/.

# Production Deployment Notes

Additional package installation notes are in the Vagrantfile.

You'll need a `data` directory that contains:

* analysis (the output of our data analyses)
* congress (a symbolic link to the [congress project](https://github.com/unitedstates/congress)'s `data` directory, holding bill and legislator data, some of which can't be reproduced because the source data is gone; also set `CONGRESS_DATA_PATH=data/congress` in local/settings.env)
* congress-bill-text-legacy (a final copy of HTML bill text scraped from the old THOMAS.gov, for bills before XML bill text started)
* historical-committee-membership (past committee membership, snapshots of earlier data)
* legislator-photos (manually collected photos of legislators; there's a symbolic link from `static/legislator-photos` to `legislator-photos/photos`)

You'll need several other data repositories that you can put in the `data` directory if you don't expose the whole directory over HTTP, but they can also be placed anywhere because the paths are in settings:

* Our [congressional misconduct database](https://github.com/govtrack/misconduct) YAML file: `MISCONDUCT_DATABASE_PATH=data/misconduct/misconduct.yaml`
* Our [legislator name pronunciation database](https://github.com/govtrack/pronunciation/): `PRONUNCIATION_DATABASE_PATH=data/pronunciation/legislators.yaml`
* Our [advocacy organization scorecards database](https://github.com/govtrack/advocacy-organization-scorecards): `SCORECARDS_DATABASE_PATH=data/advocacy-organization-scorecards/scorecards`

At this point you should be able to run `./manage.py runserver` and test that the site works.

And `conf/uwsgi_start test 1` should start the uWSGI application daemon.

Install nginx, supervisord (which keeps the uWSGI process running), and certbot and set up their configuration files:

    apt install nginx supervisor certbot python3-certbot-nginx
    rm /etc/nginx/sites-enabled/default
    ln -s /home/govtrack/web/conf/nginx.conf /etc/nginx/sites-enabled/www.govtrack.us.conf
    ln -s /home/govtrack/web/conf/supervisor.conf /etc/supervisor/conf.d/govtrack.conf
    # install a TLS certificate at /etc/ssl/local/ssl_certificate.{key,crt} (e.g. https://gist.github.com/JoshData/49eff618f84ce4890697d65bcb740137)
    service nginx restart
    service supervisor restart
    certbot # and follow prompts, but without the HTTP redirect because we already have it

To scrape and load new data, you'll need the congress project, etc.:

* Clone the congress project repo anywhere and set that directory as `CONGRESS_PROJECT_PATH` in GovTrack's `local/settings.env`.
* Follow its installation steps to create a Python 2 virtualenv for it in its `.env` directory.
* Symlink the `data/congress` _data_ directory as the `data` directory inside the congress project directory.
* Clone the [congress-legislators](https://github.com/unitedstates/congress-legislators/) project as a subdirectory and follow its installation steps to create a separate Python 3 virtualenv for its scripts in its `scripts/.env` directory.
* Try launching the scrapers from the GovTrack directory: `./run_scrapers.py people`, `./run_scrapers.py committees`, etc.
* Copy over our local/skoposlabs_s3cmd.ini file.
* Enable the crontab.

The crontab sends the outputs of the commands to Josh, so the server needs a sendmail-like command. The easiest to set up is msmtp, like so:

	apt install msmtp-mta
	cat > /etc/msmtprc <<EOF;
	account default
	auth on
	tls on
	tls_trust_file /etc/ssl/certs/ca-certificates.crt
	host *******
	port 587
	from #######@govtrack.us
	user *******
	password *******
	EOF
