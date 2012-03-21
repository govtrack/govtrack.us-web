export RELEASE=1
./parse.py -l FATAL person
./parse.py -l FATAL committee
./parse.py -l FATAL --congress=112 bill
./parse.py -l FATAL --congress=112 vote
./manage.py update_index
