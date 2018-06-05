#!/usr/bin/env python
"""Apache Log Parser

Parser for Apache log files. This is a port to python of Peter Hickman's
Apache::LogEntry Perl module:
<http://cpan.uwinnipeg.ca/~peterhi/Apache-LogRegex>

Takes the Apache logging format defined in your httpd.conf and generates
a regular expression which is used to a line from the log file and
return it as a dictionary with keys corresponding to the fields defined
in the log format.

Example:

    import apachelog, sys

    # Format copied and pasted from Apache conf - use raw string + single quotes
    format = r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'
    
    p = apachelog.parser(format)

    for line in open('/var/apache/access.log'):
        try:
           data = p.parse(line)
        except:
           sys.stderr.write("Unable to parse %s" % line)

The return dictionary from the parse method depends on the input format.
For the above example, the returned dictionary would look like;

    {
    '%>s': '200',
    '%b': '2607',
    '%h': '212.74.15.68',
    '%l': '-',
    '%r': 'GET /images/previous.png HTTP/1.1',
    '%t': '[23/Jan/2004:11:36:20 +0000]',
    '%u': '-',
    '%{Referer}i': 'http://peterhi.dyndns.org/bandwidth/index.html',
    '%{User-Agent}i': 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.2) Gecko/20021202'
    }

...given an access log entry like (split across lines for formatting);

    212.74.15.68 - - [23/Jan/2004:11:36:20 +0000] "GET /images/previous.png HTTP/1.1"
        200 2607 "http://peterhi.dyndns.org/bandwidth/index.html"
        "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.2) Gecko/20021202"

You can also re-map the field names by subclassing (or re-pointing) the
alias method.

Generally you should be able to copy and paste the format string from
your Apache configuration, but remember to place it in a raw string
using single-quotes, so that backslashes are handled correctly.

This module provides three of the most common log formats in the
formats dictionary;

    # Common Log Format (CLF)
    p = apachelog.parser(apachlog.formats['common'])

    # Common Log Format with Virtual Host
    p = apachelog.parser(apachlog.formats['vhcommon'])

    # NCSA extended/combined log format
    p = apachelog.parser(apachlog.formats['extended'])

For notes regarding performance while reading lines from a file
in Python, see <http://effbot.org/zone/readline-performance.htm>.
Further performance boost can be gained by using psyco
<http://psyco.sourceforge.net/>

On my system, using a loop like;

    for line in open('access.log'):
        p.parse(line)

...was able to parse ~60,000 lines / second. Adding psyco to the mix,
up that to ~75,000 lines / second.

The parse_date function is intended as a fast way to convert a log
date into something useful, without incurring a significant date
parsing overhead - good enough for basic stuff but will be a problem
if you need to deal with log from multiple servers in different
timezones.
"""

__version__ = "1.1"
__license__ = """Released under the same terms as Perl.
See: http://dev.perl.org/licenses/
"""
__author__ = "Harry Fuecks <hfuecks@gmail.com>"
__contributors__ = [
    "Peter Hickman <peterhi@ntlworld.com>",
    "Loic Dachary <loic@dachary.org>"
    ]
    
import re

class ApacheLogParserError(Exception):
    pass

class parser:
    
    def __init__(self, format):
        """
        Takes the log format from an Apache configuration file.

        Best just copy and paste directly from the .conf file
        and pass using a Python raw string e.g.
        
        format = r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'
        p = apachelog.parser(format)
        """
        self._names = []
        self._regex = None
        self._pattern = ''
        self._parse_format(format)
    
    def _parse_format(self, format):
        """
        Converts the input format to a regular
        expression, as well as extracting fields

        Raises an exception if it couldn't compile
        the generated regex.
        """
        format = format.strip()
        format = re.sub('[ \t]+',' ',format)
        
        subpatterns = []

        findquotes = re.compile(r'^\\"')
        findreferreragent = re.compile('Referer|User-Agent')
        findpercent = re.compile('^%.*t$')
        lstripquotes = re.compile(r'^\\"')
        rstripquotes = re.compile(r'\\"$')
        self._names = []
        
        for element in format.split(' '):

            hasquotes = 0
            if findquotes.search(element): hasquotes = 1

            if hasquotes:
                element = lstripquotes.sub('', element)
                element = rstripquotes.sub('', element)
            
            self._names.append(self.alias(element))
            
            subpattern = '(\S*)'
            
            if hasquotes:
                if element == '%r' or findreferreragent.search(element):
                    subpattern = r'\"([^"\\]*(?:\\.[^"\\]*)*)\"'
                else:
                    subpattern = r'\"([^\"]*)\"'
                
            elif findpercent.search(element):
                subpattern = r'(\[[^\]]+\])'
                
            elif element == '%U':
                subpattern = '(.+?)'
            
            subpatterns.append(subpattern)
        
        self._pattern = '^' + ' '.join(subpatterns) + '$'
        try:
            self._regex = re.compile(self._pattern)
        except Exception as e:
            raise ApacheLogParserError(e)
        
    def parse(self, line):
        """
        Parses a single line from the log file and returns
        a dictionary of it's contents.

        Raises and exception if it couldn't parse the line
        """
        line = line.strip()
        match = self._regex.match(line)
        
        if match:
            data = {}
            for k, v in zip(self._names, match.groups()):
                data[k] = v
            return data
        
        raise ApacheLogParserError("Unable to parse: %s with the %s regular expression" % ( line, self._pattern ) )

    def alias(self, name):
        """
        Override / replace this method if you want to map format
        field names to something else. This method is called
        when the parser is constructed, not when actually parsing
        a log file
        
        Takes and returns a string fieldname
        """
        return name

    def pattern(self):
        """
        Returns the compound regular expression the parser extracted
        from the input format (a string)
        """
        return self._pattern

    def names(self):
        """
        Returns the field names the parser extracted from the
        input format (a list)
        """
        return self._names

months = {
    'Jan':'01',
    'Feb':'02',
    'Mar':'03',
    'Apr':'04',
    'May':'05',
    'Jun':'06',
    'Jul':'07',
    'Aug':'08',
    'Sep':'09',
    'Oct':'10',
    'Nov':'11',
    'Dec':'12'
    }

def parse_date(date):
    """
    Takes a date in the format: [05/Dec/2006:10:51:44 +0000]
    (including square brackets) and returns a two element
    tuple containing first a timestamp of the form
    YYYYMMDDHH24IISS e.g. 20061205105144 and second the
    timezone offset as is e.g.;

    parse_date('[05/Dec/2006:10:51:44 +0000]')  
    >> ('20061205105144', '+0000')

    It does not attempt to adjust the timestamp according
    to the timezone - this is your problem.
    """
    date = date[1:-1]
    elems = [
        date[7:11],
        months[date[3:6]],
        date[0:2],
        date[12:14],
        date[15:17],
        date[18:20],
        ]
    return (''.join(elems),date[21:])


"""
Frequenty used log formats stored here
"""
formats = {
    # Common Log Format (CLF)
    'common':r'%h %l %u %t \"%r\" %>s %b',

    # Common Log Format with Virtual Host
    'vhcommon':r'%v %h %l %u %t \"%r\" %>s %b',

    # NCSA extended/combined log format
    'extended':r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\"',
    }

if __name__ == '__main__':
    import unittest

    class TestApacheLogParser(unittest.TestCase):

        def setUp(self):
            self.format = r'%h %l %u %t \"%r\" %>s '\
                          r'%b \"%{Referer}i\" \"%{User-Agent}i\"'
            self.fields = '%h %l %u %t %r %>s %b %{Referer}i '\
                          '%{User-Agent}i'.split(' ')
            self.pattern = '^(\\S*) (\\S*) (\\S*) (\\[[^\\]]+\\]) '\
                           '\\\"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)\\\" '\
                           '(\\S*) (\\S*) \\\"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)\\\" '\
                           '\\\"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)\\\"$'
            self.line1  = r'212.74.15.68 - - [23/Jan/2004:11:36:20 +0000] '\
                          r'"GET /images/previous.png HTTP/1.1" 200 2607 '\
                          r'"http://peterhi.dyndns.org/bandwidth/index.html" '\
                          r'"Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.2) '\
                          r'Gecko/20021202"'
            self.line2  = r'212.74.15.68 - - [23/Jan/2004:11:36:20 +0000] '\
                          r'"GET /images/previous.png=\" HTTP/1.1" 200 2607 '\
                          r'"http://peterhi.dyndns.org/bandwidth/index.html" '\
                          r'"Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.2) '\
                          r'Gecko/20021202"'
            self.line3  = r'4.224.234.46 - - [20/Jul/2004:13:18:55 -0700] '\
                          r'"GET /core/listing/pl_boat_detail.jsp?&units=Feet&checked'\
                          r'_boats=1176818&slim=broker&&hosturl=giffordmarine&&ywo='\
                          r'giffordmarine& HTTP/1.1" 200 2888 "http://search.yahoo.com/'\
                          r'bin/search?p=\"grady%20white%20306%20bimini\"" '\
                          r'"Mozilla/4.0 (compatible; MSIE 6.0; Windows 98; '\
                          r'YPC 3.0.3; yplus 4.0.00d)"'
            self.p = parser(self.format)

        def testpattern(self):
            self.assertEqual(self.pattern, self.p.pattern())

        def testnames(self):
            self.assertEqual(self.fields, self.p.names())

        def testline1(self):
            data = self.p.parse(self.line1)
            self.assertEqual(data['%h'], '212.74.15.68', msg = 'Line 1 %h')
            self.assertEqual(data['%l'], '-', msg = 'Line 1 %l')
            self.assertEqual(data['%u'], '-', msg = 'Line 1 %u')
            self.assertEqual(data['%t'], '[23/Jan/2004:11:36:20 +0000]', msg = 'Line 1 %t')
            self.assertEqual(
                data['%r'],
                'GET /images/previous.png HTTP/1.1',
                msg = 'Line 1 %r'
                )
            self.assertEqual(data['%>s'], '200', msg = 'Line 1 %>s')
            self.assertEqual(data['%b'], '2607', msg = 'Line 1 %b')
            self.assertEqual(
                data['%{Referer}i'],
                'http://peterhi.dyndns.org/bandwidth/index.html',
                msg = 'Line 1 %{Referer}i'
                )
            self.assertEqual(
                data['%{User-Agent}i'],
                'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.2) Gecko/20021202',
                msg = 'Line 1 %{User-Agent}i'
                )

        
        def testline2(self):
            data = self.p.parse(self.line2)
            self.assertEqual(data['%h'], '212.74.15.68', msg = 'Line 2 %h')
            self.assertEqual(data['%l'], '-', msg = 'Line 2 %l')
            self.assertEqual(data['%u'], '-', msg = 'Line 2 %u')
            self.assertEqual(
                data['%t'],
                '[23/Jan/2004:11:36:20 +0000]',
                msg = 'Line 2 %t'
                )
            self.assertEqual(
                data['%r'],
                r'GET /images/previous.png=\" HTTP/1.1',
                msg = 'Line 2 %r'
                )
            self.assertEqual(data['%>s'], '200', msg = 'Line 2 %>s')
            self.assertEqual(data['%b'], '2607', msg = 'Line 2 %b')
            self.assertEqual(
                data['%{Referer}i'],
                'http://peterhi.dyndns.org/bandwidth/index.html',
                msg = 'Line 2 %{Referer}i'
                )
            self.assertEqual(
                data['%{User-Agent}i'],
                'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.2) Gecko/20021202',
                msg = 'Line 2 %{User-Agent}i'
                )

        def testline3(self):
            data = self.p.parse(self.line3)
            self.assertEqual(data['%h'], '4.224.234.46', msg = 'Line 3 %h')
            self.assertEqual(data['%l'], '-', msg = 'Line 3 %l')
            self.assertEqual(data['%u'], '-', msg = 'Line 3 %u')
            self.assertEqual(
                data['%t'],
                '[20/Jul/2004:13:18:55 -0700]',
                msg = 'Line 3 %t'
                )
            self.assertEqual(
                data['%r'],
                r'GET /core/listing/pl_boat_detail.jsp?&units=Feet&checked_boats='\
                r'1176818&slim=broker&&hosturl=giffordmarine&&ywo=giffordmarine& '\
                r'HTTP/1.1',
                msg = 'Line 3 %r'
                )
            self.assertEqual(data['%>s'], '200', msg = 'Line 3 %>s')
            self.assertEqual(data['%b'], '2888', msg = 'Line 3 %b')
            self.assertEqual(
                data['%{Referer}i'],
                r'http://search.yahoo.com/bin/search?p=\"grady%20white%20306'\
                r'%20bimini\"',
                msg = 'Line 3 %{Referer}i'
                )
            self.assertEqual(
                data['%{User-Agent}i'],
                'Mozilla/4.0 (compatible; MSIE 6.0; Windows 98; YPC 3.0.3; '\
                'yplus 4.0.00d)',
                msg = 'Line 3 %{User-Agent}i'
                )


        def testjunkline(self):
            self.assertRaises(ApacheLogParserError,self.p.parse,'foobar')

        def testhasquotesaltn(self):
            p = parser(r'%a \"%b\" %c')
            line = r'foo "xyz" bar'
            data = p.parse(line)
            self.assertEqual(data['%a'],'foo', '%a')
            self.assertEqual(data['%b'],'xyz', '%c')
            self.assertEqual(data['%c'],'bar', '%c')

        def testparsedate(self):
            date = '[05/Dec/2006:10:51:44 +0000]'
            self.assertEqual(('20061205105144','+0000'),parse_date(date))

    unittest.main()
