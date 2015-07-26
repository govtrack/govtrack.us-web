GovTrack website frontend
=========================

This repo contains the source code of the front-end for www.GovTrack.us.
The data-gathering scripts are elsewhere.

Installation
------------

GovTrack.us runs on Ubuntu 12.10 or OS X

* Install dependencies via OS package manager:

  ```
  apt-get install git python-virtualenv python-lxml python-openid python-oauth2 \
      python-iso8601 python-numpy python-scipy python-prctl
  ```

  or for OS X (xCode required)
  ```
  export CFLAGS=-I/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.10.sdk/usr/include/libxml2
  pip install virtualenv lxml python-openid python-oauth2 \
      iso-8601 numpy scipy
  ```

* Clone the source code. Besides this project, you'll also need [@unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) which is where legislator and committee information come from.

  ```
  git clone https://github.com/unitedstates/congress-legislators   
  git clone --recursive https://github.com/govtrack/govtrack.us-web.git
  ```

* Change directory to the source code root:

  ```
  cd ./govtrack.us-web/
  ```

* (OS X only) Install bcrypt http://stackoverflow.com/questions/22875270/error-installing-bcrypt-with-pip-on-os-x-cant-find-ffi-h-libffi-is-installed

* Run the build script to install additional dependencies into a virtual environment:

  ```
  ./build/buildenv.sh
  ```

* Create a local settings file based on the example file:

  ```
  cp settings_local.example.py settings_local.py
  ```

* Edit `settings_local.py` to set up your database. The default configuration uses SQLite as the database and no database configuration is required. Fill in SECRET_KEY though. Here's how you can generate a SECRET_KEY:

  ```
  ./manage.py generate_secret_key
  ```

* To enable search (for which complete instructions haven't been provided, so really skip this):

  * Install Solr:

    ```
    apt-get install openjdk-7-jre jetty
    ```

  * Follow the instructions at:

    http://django-haystack.readthedocs.org/en/latest/installing_search_engines.html#solr

  * Symlink `./bill/solr_schema.xml` to `./solr/conf/schema.xml`.

* Initialize the database and minify some files:

  ```
  ./manage.py migrate
  ./minify
  ```
* Load some data:

  ```
  wget http://www.govtrack.us/data/db/django-fixture-{people,usc_sections,billterms}.json
  ./manage.py loaddata django-fixture-people.json
  ./manage.py loaddata django-fixture-usc_sections.json
  ./manage.py loaddata django-fixture-billterms.json
  
  ./parse.py person
  ./parse.py committee # fails b/c meeting data not available

  ./build/rsync.sh
  ./parse.py bill --congress=114 --disable-index --disable-events
  ./parse.py vote --congress=114 --disable-index --disable-events
  ```
  
If you configured Solr, you can remove --disable-index. For the sake of speed, --disable-events will skip the creation of the events table for bills, which is the basis for feeds and tracking, so that will be nonfunctional.

* Check the site works by running the development server and visiting the URL specified by the runserver process.

  ```
  ./manage.py runserver
  ```

* To update the data in the future, first git-pull the congress-legislators repo to get the latest legislator information. Then:

  ```
  build/rsync.sh
  ./parse.py person
  ./parse.py committee --congress=113
  ./parse.py bill --congress=113
  ./parse.py vote --congress=113
  ```

* TODO: We haven't set up any search indexing, so all of the search pages will come up empty.
