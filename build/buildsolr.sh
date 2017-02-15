set -e

GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

# First stop the jetty service, as we won't be able to successfully stop the
# running process after we overwrite the configuration.
sudo service jetty8 stop

# Download and unzip the solr installation package
if [ ! -f solr-4.10.2.tgz ]
then
  curl -LO https://archive.apache.org/dist/lucene/solr/4.10.2/solr-4.10.2.tgz
fi

if [ ! -d solr-4.10.2 ]
then
  tar xvzf solr-4.10.2.tgz
fi

cd solr-4.10.2

# Create a new configuration from the example
cp -R example govtrack

# Initialize a collection for each of bill and person types
mv govtrack/solr/collection1 govtrack/solr/bill
echo "name=bill" > govtrack/solr/bill/core.properties
ln -f -s govtrack/solr/bill/conf/schema.xml $GOVTRACK_ROOT/bill/solr/schema.xml

cp -R govtrack/solr/bill govtrack/solr/person
echo "name=person" > govtrack/solr/person/core.properties
ln -f -s govtrack/solr/person/conf/schema.xml $GOVTRACK_ROOT/person/solr/schema.xml

# Copy Solr over to /opt
sudo cp -R govtrack /opt/solr

# Set up jetty to serve Solr
sudo cp $GOVTRACK_ROOT/build/solrconfig/jetty /etc/default/jetty8
sudo cp $GOVTRACK_ROOT/build/solrconfig/jetty-logging.xml /opt/solr/etc/jetty-logging.xml

sudo useradd -d /opt/solr -s /sbin/false solr
sudo mkdir -p /var/log/solr
sudo chown solr:solr -R /opt/solr
sudo chown solr:solr -R /var/log/solr
