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
    varkey = None
    attrs = set()
    for fname in glob.glob('data/us/112/rolls/*.xml'):
        tree = etree.parse(fname)
        for count, item in enumerate(tree.xpath('/roll')):
            attrs.update(item.attrib.keys())
            for subitem in item.xpath('./option'):
                vars.add(subitem.get('key'))
            if varkey:
                if varkey in item.attrib:
                    vars.add(item.get(varkey))
    print varkey, vars
    print 'Attributes: %s' % ', '.join(attrs)


if __name__ == '__main__':
    main()
