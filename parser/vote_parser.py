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
from person.models import Person
from vote.models import Vote, VoteOption, VoteSource, Voter, CongressChamber


class VoteProcessor(Processor):
    """
    Parser of /roll records.
    """

    REQUIRED_ATTRIBUTES = ['source', 'datetime']
    ATTRIBUTES = ['source', 'datetime']
    REQUIRED_NODES = ['type', 'question', 'required', 'result']
    NODES = ['type', 'question', 'required', 'result']
    FIELD_MAPPING = {'datetime': 'created', 'type': 'vote_type'}
    SOURCE_MAPPING = {'senate.gov': VoteSource.senate,
                      'house.gov': VoteSource.house,
                      'keithpoole': VoteSource.keithpoole}

    def source_handler(self, value):
        return self.SOURCE_MAPPING[value]

    def datetime_handler(self, value):
        try:
            return datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            try:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-05:00')
            except ValueError:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-04:00') - timedelta(hours=1)


class VoteOptionProcessor(Processor):
    "Parser of /roll/option nodes"

    REQUIRED_ATTRIBUTES = ['key']
    ATTRIBUTES = ['key']

    def process_text(self, obj, node):
        obj.value = node.text


class VoterProcessor(Processor):
    "Parser of /roll/voter nodes"

    def process(self, options, *args, **kwargs):
        self.options = options
        return super(VoterProcessor, self).process(*args, **kwargs)

    REQUIRED_ATTRIBUTES = ['id', 'vote']
    ATTRIBUTES = ['id', 'vote']
    FIELD_MAPPING = {'id': 'person', 'vote': 'option'}
    PERSON_CACHE = {}

    def id_handler(self, value):
        return self.PERSON_CACHE[int(value)]

    def vote_handler(self, value):
        return self.options[value]


def main():
    "Main parser logic"

    vote_processor = VoteProcessor()
    option_processor = VoteOptionProcessor()
    voter_processor = VoterProcessor()
    voter_processor.PERSON_CACHE = dict((x.pk, x) for x in Person.objects.all())
    Vote.objects.all().delete()

    re_path = re.compile('data/us/(\d+)/rolls/([hs])(\w+)-(\d+)\.xml')
    chamber_mapping = {'s': CongressChamber.senate,
                       'h': CongressChamber.house}

    files = glob.glob('data/us/*/rolls/*.xml')
    print 'Processing votes: %d files' % len(files)
    total = len(files)
    progress = Progress(total=total, name='files', step=10)
    for fname in files:
        try:
            progress.tick()
            tree = etree.parse(fname)
            for roll_node in tree.xpath('/roll'):
                vote = vote_processor.process(Vote(), roll_node)
                match = re_path.search(fname)
                vote.congress = match.group(1)
                vote.chamber = chamber_mapping[match.group(2)]
                vote.session = match.group(3)
                vote.number = match.group(4)
                vote.save()

                options = {}
                for option_node in roll_node.xpath('./option'):
                    option = option_processor.process(VoteOption(), option_node)
                    option.vote = vote
                    option.save()
                    options[option.key] = option

                for voter_node in roll_node.xpath('./voter'):
                    voter = voter_processor.process(options, Voter(), voter_node)
                    voter.vote = vote
                    voter.created = vote.created
                    #voter.save()

        except Exception, ex:
            logging.error('', exc_info=ex)
            print 'File name: %s' % fname


def find():
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
