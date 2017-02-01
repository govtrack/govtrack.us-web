GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

# Download and unzip the solr installation package
curl -LO https://archive.apache.org/dist/lucene/solr/4.10.2/solr-4.10.2.tgz
tar xvzf solr-4.10.2.tgz
cd solr-4.10.2

# Create a new configuration from the example
cp -R example govtrack

# Initialize a collection for each of bill and person types
mv govtrack/collection1 govtrack/bill
echo "name=bill" > govtrack/bill/core.properties
ln -s govtrack/bill/conf/schema.xml $GOVTRACK_ROOT/bill/solr/schema.xml

cp -R govtrack/bill govtrack/person
echo "name=person" > govtrack/person/core.properties
ln -s govtrack/person/conf/schema.xml $GOVTRACK_ROOT/person/solr/schema.xml

# Copy Solr over to /opt
sudo cp -R govtrack /opt/solr

# Set up jetty to serve Solr
sudo cp $GOVTRACK_ROOT/build/solrconfig/jetty /etc/default/jetty8
sudo cp $GOVTRACK_ROOT/build/solrconfig/jetty-logging.xml /opt/solr/etc/jetty-logging.xml

sudo useradd -d /opt/solr -s /sbin/false solr
sudo mkdir /var/log/solr
sudo chown solr:solr -R /opt/solr
sudo chown solr:solr -R /var/log/solr
