GovTrack website frontend

This repo contains the source code of the front-end for www.GovTrack.us.
The data-gathering scripts are elsewhere.

Installation
============

* Clone the source code:

  git clone --recursive https://github.com/govtrack/govtrack.us-web.git

* Change directory to the source code root:

  cd ./govtrack.us-web/

* Create a local settings file based on the example file:

  cp settings_local.example.py settings_local.py

* Edit settings_local.py to include your various credentials.

* Install dependencies via OS package manager:

  apt-get install python-virtualenv python-lxml python-openid python-oauth2 \
     python-iso8601 python-numpy

* Run the build script to install additional dependencies into a virtual environment:

  ./build/buildenv.sh

* For search, install Solr:

  apt-get install openjdk-7-jre jetty

  Follow the instructions at:
  http://django-haystack.readthedocs.org/en/latest/installing_search_engines.html#solr

  Symlink bill/solr_schema.xml into solr/conf/schema.xml

* Initialize the database and minify some files:

  ./manage.py syncdb
  ./manage.py runserver
  ./minify

* Check the site works by visiting the URL specified by the runserver process.

* Get the data files:

  ./build/rsync.sh

* Load the data:

  ./run_parsers.sh

