"""
Parser of data/us/committees.xml
"""
from lxml import etree
from datetime import datetime
import glob
import re
import logging

from parser.progress import Progress
from parser.processor import Processor


def main():
    "Method for testing different things"

    vars = set()
    for fname in glob.glob('data/us/*/rolls/*.xml'):
        tree = etree.parse(fname)
        for node in tree.xpath('//option'):
            vars.add((node.get('key'), node.text))
    for item in vars:
        print item


"""
data/us/109/rolls/s2005-363.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/107/rolls/s2001-79.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/107/rolls/s2002-119.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/107/rolls/s2001-65.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/110/rolls/s2008-47.xml
{'VP': '1', 'vote': '+', 'id': '0', 'value': 'Yea'}
data/us/106/rolls/s1999-134.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/108/rolls/s2003-171.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/108/rolls/s2003-196.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/108/rolls/s2003-134.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/103/rolls/s1993-247.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/103/rolls/s1993-190.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}
data/us/103/rolls/s1994-255.xml
{'VP': '1', 'vote': '', 'id': '0', 'value': ''}



data/us/38/rolls/h1-291.xml
{'vote': '-', 'state': '', 'district': '', 'id': '0', 'value': 'Nay'}
data/us/38/rolls/h1-335.xml
{'vote': '-', 'state': '', 'district': '', 'id': '0', 'value': 'Nay'}
data/us/38/rolls/h2-457.xml
{'vote': '0', 'state': '', 'district': '', 'id': '0', 'value': 'Not Voting'}
data/us/38/rolls/h1-140.xml
{'vote': '+', 'state': '', 'district': '', 'id': '0', 'value': 'Aye'}
data/us/38/rolls/h1-39.xml
{'vote': '0', 'state': '', 'district': '', 'id': '0', 'value': 'Not Voting'}
data/us/87/rolls/h1961-1.xml
{'vote': '-', 'state': '', 'district': '', 'id': '0', 'value': 'Nay'}

"""


if __name__ == '__main__':
    main()
