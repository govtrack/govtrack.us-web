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
      python-iso8601 python-scipy python-prctl
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

* Edit `settings_local.py` to set up your database. The default configuration uses SQLite as the database and no database configuration is required. Fill in SECRET\_KEY though. Here's how you can generate a SECRET\_KEY:

  ```
  ./manage.py generate_secret_key
  ```

* To enable search (for which complete instructions haven't been provided, so really skip this):

  * For debugging, install Xapian and add it to the virtual environment:

    ```
    apt-get install python-xapian
    ln -s /usr/lib/python2.7/dist-packages/xapian/ .env/local/lib/python2.7/xapian

    ```

  * Set HAYSTACK\_CONNECTIONS:

    ```
    HAYSTACK_CONNECTIONS = {
      ...
      'person': {
          'ENGINE': 'xapian_backend.XapianEngine',
          'PATH': os.path.join(os.path.dirname(__file__), 'xapian_index_person'),
      },
      'bill': {
          'ENGINE': 'xapian_backend.XapianEngine',
          'PATH': os.path.join(os.path.dirname(__file__), 'xapian_index_bill'),
      },
      ...
    }                   
    ```

  * For production, install Solr:

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
  ```

* If you set up search indexing, update the index of people:

  ```
  ./manage.py update_index -u person person
  ```

* Load bills and votes data:

  ```
  ./build/rsync.sh
  ./parse.py bill --congress=114 --disable-index --disable-events
  ./parse.py vote --congress=114 --disable-index --disable-events
  ```
  
If you configured Solr, you can remove --disable-index. For the sake of speed, --disable-events will skip the creation of the events table for bills, which is the basis for feeds and tracking, so that will be nonfunctional.

* Check the site works by running the development server and visiting the URL specified by the runserver process.

  ```
  ./manage.py runserver
  ```

* Create an account for yourself, (without setting up an email server) by running the `createsuperuser` command.

  ```
  ./manage.py createsuperuser
  ```

* To update the data in the future, first git-pull the congress-legislators repo to get the latest legislator information. Then:

  ```
  build/rsync.sh
  ./parse.py person
  ./parse.py committee --congress=113
  ./parse.py bill --congress=113
  ./parse.py vote --congress=113
  ```

# Credits

Emoji icons by http://emojione.com/developers/.
