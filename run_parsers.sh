export RELEASE=1
./parse.py -l ERROR person
./parse.py -l ERROR committee
./parse.py -l ERROR --congress=112 bill
./parse.py -l ERROR --congress=112 vote
#./parse.py -l ERROR states
./manage.py update_index person

# bills are indexed as they are parsed
#
# state bills are indexed in a separate index, so for maintenance:
# ./manage.py update_index states --using states
