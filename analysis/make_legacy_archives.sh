#!/bin/bash

# Make archives of scraped data from THOMAS that is not available
# anywhere else anymore.

# files/congress-bill-text-legacy.tgz
# Archhive of HTML-formatted bill text taken from THOMAS.

# files/congress-bill-status-legacy.tgz
# Archive of bill status JSON files from THOMAS.
find data/congress/{93..113}/bills -name text-versions -prune -or -name data.json -print \
	| sed "s#^data/##" \
	| pv -l \
	| tar -czf files/congress-bill-status-legacy.tgz -C data -T -

# files/congress-amendment-status-legacy.tgz
# Archive of amendment status JSON files from THOMAS.
find data/congress/{97..113}/amendments -name data.json \
	| sed "s#^data/##" \
	| pv -l \
	| tar -czf files/congress-amendment-status-legacy.tgz -C data -T -

