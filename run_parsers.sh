export RELEASE=1
./parse.py -l ERROR person
./parse.py -l ERROR committee
./parse.py -l ERROR --congress=112 bill
./parse.py -l ERROR --congress=112 vote
#./parse.py -l ERROR states

# -v 0 sets low verbosity
./manage.py update_index -v 0 -u person person

# bills and state bills are indexed as they are parsed, but to
# freshen the index:
# ./manage.py update_index -v 2 -u bill bill
# ./manage.py update_index -v 2 -u states states

# To clear an index, access elasticsearch directly. Haystack
# has a problem deleting an index. e.g.:
# curl -XDELETE 'http://localhost:9200/person'

