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
    for fname in glob.glob('data/us/112/rolls/*.xml'):
        tree = etree.parse(fname)
        cats = tree.xpath('//category')
        if len(cats) > 1:
            raise Exception('More then one cat in %s' % fname)
        elif len(cats) == 0:
            pass
        else:
            vars.add(cats[0].text)
    print 'Categories:'
    print '\n'.join(vars)


if __name__ == '__main__':
    main()
