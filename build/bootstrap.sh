sudo apt-get update
sudo apt-get install -y git python-virtualenv python-lxml python-openid python-oauth2     python-iso8601 python-numpy python-scipy sqlite3

git clone https://github.com/unitedstates/congress-legislators   
git clone --recursive https://github.com/govtrack/govtrack.us-web.git
cd ./govtrack.us-web/

./build/buildenv.sh

cp settings_local.example.py settings_local.py
sed -i "s/^SECRET_KEY.*/SECRET_KEY='$(./manage.py generate_secret_key | sed -e 's/&/\\&/g')'/" settings_local.py

./manage.py syncdb --noinput
./minify

wget http://www.govtrack.us/data/db/django-fixture-{people,usc_sections,billterms}.json
./manage.py loaddata django-fixture-people.json
./manage.py loaddata django-fixture-usc_sections.json
./manage.py loaddata django-fixture-billterms.json

./parse.py committee

build/rsync.sh
./parse.py bill --congress=113 --disable-index --disable-events
./parse.py vote --congress=113 --disable-index --disable-events
