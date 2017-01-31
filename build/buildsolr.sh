GOVTRACK_ROOT=$(realpath $(dirname $0)/..)

# Download and unzip the solr installation package
curl -LO https://archive.apache.org/dist/lucene/solr/4.10.2/solr-4.10.2.tgz
tar xvzf solr-4.10.2.tgz
cd solr-4.10.2

# Create a new configuration from the example
cp -R example govtrack_solr

# Initialize a collection for each of bill and person types
mv solr/collection1 solr/bill
echo "name=bill" > solr/bill/core.properties
ln -s solr/bill/conf/schema.xml $GOVTRACK_ROOT/bill/solr/schema.xml

cp -R solr/bill solr/person
echo "name=person" > solr/person/core.properties
ln -s solr/person/conf/schema.xml $GOVTRACK_ROOT/person/solr/schema.xml
