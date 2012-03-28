export RELEASE=1
./parse.py -l ERROR person
./parse.py -l ERROR committee
./parse.py -l ERROR --congress=112 bill
./parse.py -l ERROR --congress=112 vote
./manage.py update_index
