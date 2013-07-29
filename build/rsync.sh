rsync -avz --delete --delete-excluded govtrack.us::govtrackdata data \
	--exclude "rdf" --exclude "misc" --exclude "db" \
	--exclude "us/bills.text*" --exclude "us/*/cr" \
	--exclude "**/repstats" --exclude "**/repstats.person" \
	--exclude "**/bills.amdt" --exclude "**/bills.cbo" --exclude "**/bills.ombsap" \
	--exclude "photos" \
	--exclude "congress" \
	--exclude "congress-legislators" \
	--include "us/113" --exclude "us/[0-9]*"
