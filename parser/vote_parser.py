"""
Parser of data/us/committees.xml
"""
from lxml import etree
import glob
import re
import logging

from parser.progress import Progress
from parser.processor import Processor
from person.models import Person
from parser.models import File
from vote.models import (Vote, VoteOption, VoteSource, Voter,
                         CongressChamber, VoteCategory, VoterType)


class VoteProcessor(Processor):
    """
    Parser of /roll records.
    """

    REQUIRED_ATTRIBUTES = ['source', 'datetime']
    ATTRIBUTES = ['source', 'datetime']
    REQUIRED_NODES = ['type', 'question', 'required', 'result']
    NODES = ['type', 'question', 'required', 'result', 'category']
    FIELD_MAPPING = {'datetime': 'created', 'type': 'vote_type'}
    SOURCE_MAPPING = {
        'senate.gov': VoteSource.senate,
        'house.gov': VoteSource.house,
        'keithpoole': VoteSource.keithpoole,
    }
    DEFAULT_VALUES = {'category': 'other'}
    CATEGORY_MAPPING = {
        'amendment': VoteCategory.amendment,
        'passage-suspension': VoteCategory.passage_suspension,
        'passage': VoteCategory.passage,
        'cloture': VoteCategory.cloture,
        'passage-part': VoteCategory.passage_part,
        'nomination': VoteCategory.nomination,
        'procedural': VoteCategory.procedural,
        'other': VoteCategory.other,
    }

    def category_handler(self, value):
        return self.CATEGORY_MAPPING[value]

    def source_handler(self, value):
        return self.SOURCE_MAPPING[value]

    def datetime_handler(self, value):
        return Processor.parse_datetime(value)

class VoteOptionProcessor(Processor):
    "Parser of /roll/option nodes"

    REQUIRED_ATTRIBUTES = ['key']
    ATTRIBUTES = ['key']

    def process_text(self, obj, node):
        obj.value = node.text


class VoterProcessor(Processor):
    "Parser of /roll/voter nodes"

    REQUIRED_ATTRIBUTES = ['id', 'vote']
    ATTRIBUTES = ['id', 'vote']
    FIELD_MAPPING = {'id': 'person', 'vote': 'option'}
    PERSON_CACHE = {}

    def process(self, options, obj, node):
        self.options = options
        obj = super(VoterProcessor, self).process(obj, node)

        if node.get('VP') == '1':
            obj.voter_type = VoterType.vice_president
        elif node.get('id') == '0':
            obj.voter_type = VoterType.unknown
        else:
            obj.voter_type = VoterType.member

        return obj


    def id_handler(self, value):
        if int(value):
            return self.PERSON_CACHE[int(value)]
        else:
            return None

    def vote_handler(self, value):
        return self.options[value]


def main():
    """
    Parse rolls.
    """

    # Setup XML processors
    vote_processor = VoteProcessor()
    option_processor = VoteOptionProcessor()
    voter_processor = VoterProcessor()
    voter_processor.PERSON_CACHE = dict((x.pk, x) for x in Person.objects.all())

    # Remove old votes
    Vote.objects.all().delete()

    # The pattern which the roll file matches
    # Filename contains info which should be placed to DB
    # along with info extracted from the XML file
    re_path = re.compile('data/us/(\d+)/rolls/([hs])(\w+)-(\d+)\.xml')

    chamber_mapping = {'s': CongressChamber.senate,
                       'h': CongressChamber.house}

    files = glob.glob('data/us/112/rolls/*.xml')
    #files = glob.glob('data/us/38/rolls/h1-291.xml')
    print 'Processing votes: %d files' % len(files)
    total = len(files)
    progress = Progress(total=total, name='files', step=10)

    for fname in files:
        try:
            progress.tick()

            # TODO:
            # Check that file changed
            # If yes then deleted Vote::* objects related
            # to that file else do not process the file
            tree = etree.parse(fname)

            # Process role object
            for roll_node in tree.xpath('/roll'):
                vote = vote_processor.process(Vote(), roll_node)
                match = re_path.search(fname)
                vote.congress = match.group(1)
                vote.chamber = chamber_mapping[match.group(2)]
                vote.session = match.group(3)
                vote.number = match.group(4)
                vote.save()
				
                # Process roll options
                options = {}
                for option_node in roll_node.xpath('./option'):
                    option = option_processor.process(VoteOption(), option_node)
                    option.vote = vote
                    option.save()
                    options[option.key] = option

                # Process roll voters
                for voter_node in roll_node.xpath('./voter'):
                    voter = voter_processor.process(options, Voter(), voter_node)
                    voter.vote = vote
                    voter.created = vote.created
                    voter.save()

                vote.calculate_totals()

                vote.create_event()

            # TODO:
            # Update file checksum in the DB

            # TODO:
            # data/us/112/rolls/h2011-2.xml
            # produces error: Warning: Data truncated for column 'key' at row 1

        except Exception, ex:
            logging.error('', exc_info=ex)
            print 'File name: %s' % fname


if __name__ == '__main__':
    main()
