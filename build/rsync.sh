rsync -avz --delete --delete-excluded govtrack.us::govtrackdata data \
	--exclude "us/bills.text*" --exclude rdf --exclude "**/repstats" \
	--exclude "**/repstats.person" --exclude "**/index.*" --exclude "us/gis" \
	--exclude "us/fec" --exclude "us/*/cr" --exclude "**/gen.*" \
	--exclude "**/bills.cbo" --exclude "**/bills.ombsap" --exclude misc/database.sql.gz
