"""
Parser of data/us/committees.xml
"""
from lxml import etree
from datetime import datetime
import glob
import re
import logging

from common.progress import Progress
from parser.processor import Processor

def main(options):
    "Method for testing different things"

    vars = set()
    files = glob.glob('data/us/*/bills/*.xml')
    progress = Progress(total=len(files))
    for fname in files:
        progress.tick()
        for event, elem in etree.iterparse(fname, events=('end',), tag='title'):
            vars.add((elem.get('type'), elem.get('as')))
    for item in vars:
        print item


if __name__ == '__main__':
    main()
