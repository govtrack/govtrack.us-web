export RELEASE=1
./parse.py -l ERROR person
./parse.py -l ERROR committee
./parse.py -l ERROR --congress=113 bill
./parse.py -l ERROR --congress=113 vote
#./parse.py -l ERROR states

# -v 0 sets low verbosity
./manage.py update_index -v 0 -u person person

# bills and state bills are indexed as they are parsed, but to
# freshen the index. Because bills index full text and so
# indexing each time is substantial, set the TIMEOUT and
# BATCH_SIZE options in the haystack connections appropriately.
# ./manage.py update_index -v 2 -u bill bill
# ./manage.py update_index -v 2 -u states states

