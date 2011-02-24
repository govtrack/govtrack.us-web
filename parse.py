#!.env/bin/python
from common.system import setup_django
setup_django(__file__)
from optparse import OptionParser
import sys

PARSER_USAGE = """Usage: %prog action
Available actions: person, commitee, vote"""

def main():
    parser = OptionParser(usage=PARSER_USAGE)
    parser.add_option('-m', '--method', default='main',
                      help='Which parser method should be run')
    kwargs, args = parser.parse_args()
    if not args:
        parser.print_usage()
        sys.exit()
    parser = __import__('parser.%s_parser' % args[0], globals(), locals(), ['xxx'])
    getattr(parser, kwargs.method)()
    print 'Done'


if __name__ == '__main__':
    main()
