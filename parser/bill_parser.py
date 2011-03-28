"""
Parser of:
 * bill terms located in data/us/[liv, liv111, crsnet].xml
 * bills located in data/us/*/bills/*.xml
"""
from lxml import etree
import logging
from django.db.utils import IntegrityError
import glob
import re

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from bill.models import BillTerm, TermType, BillType, Bill, Cosponsor, BillStatus
from person.models import Person
from bill.title import get_primary_bill_title
from committee.models import Committee

log = logging.getLogger('parser.bill_parser')
PERSON_CACHE = {}
TERM_CACHE = {}

def get_person(pk):
    global PERSON_CACHE
    pk = int(pk)
    if not PERSON_CACHE:
        PERSON_CACHE = dict((x.pk, x) for x in Person.objects.all())
    return PERSON_CACHE[pk]


def normalize_name(name):
    "Convert name to common format."

    name = re.sub(r'\s{2,}', ' ', name)
    return name.lower()


def get_term(name):
    global TERM_CACHE
    if not TERM_CACHE:
        for term in BillTerm.objects.all():
            TERM_CACHE.setdefault(normalize_name(term.name), []).append(term)
    return TERM_CACHE[normalize_name(name)]


class TermProcessor(Processor):
    REQUIRED_ATTRIBUTES = ['value']
    ATTRIBUTES = ['value']
    FIELD_MAPPING = {'value': 'name'}


class BillProcessor(Processor):
    REQUIRED_ATTRIBUTES = ['type', 'session', 'number']
    ATTRIBUTES = ['type', 'session', 'number']
    FIELD_MAPPING = {'type': 'bill_type', 'session': 'congress'}

    def type_handler(self, value):
        return BillType.by_xml_code(value)

    def process(self, obj, node):
        obj = super(BillProcessor, self).process(obj, node)
        self.process_titles(obj, node)
        self.process_sponsor(obj, node)
        self.process_introduced(obj, node)
        self.process_current_status(obj, node)
        obj.save()
        self.process_committees(obj, node)
        self.process_terms(obj, node)
        self.process_consponsors(obj, node)
        return obj

    def process_introduced(self, obj, node):
        elem = node.xpath('./introduced')[0]
        obj.introduced_date = self.parse_datetime(elem.get('datetime'))

    def process_current_status(self, obj, node):
        elem = node.xpath('./state')[0]
        obj.current_status_date = self.parse_datetime(elem.get('datetime'))
        obj.current_status = BillStatus.by_xml_code(elem.text)

    def process_titles(self, obj, node):
        titles = []
        for elem in node.xpath('./titles/title'):
            text = unicode(elem.text) if elem.text else None
            titles.append((elem.get('type'), elem.get('as'), text))
        obj.titles = titles
        obj.title = get_primary_bill_title(obj, titles)

    def process_sponsor(self, obj, node):
        try:
            obj.sponsor = get_person(node.xpath('./sponsor')[0].get('id'))
        except IndexError:
            obj.sponsor = None

    def process_consponsors(self, obj, node):
        for subnode in node.xpath('./cosponsors/cosponsor'):
            try:
                person = get_person(subnode.get('id'))
            except IndexError:
                pass
            else:
                joined = self.parse_datetime(subnode.get('joined'))

                value = subnode.get('withdrawn')
                withdrawn = self.parse_datetime(value) if value else None
                Cosponsor.objects.create(person=person, bill=obj, joined=joined,
                                         withdrawn=withdrawn)


    def session_handler(self, value):
        return int(value)

    def process_committees(self, obj, node):
        items = []
        for subnode in node.xpath('./committees/committee'):
            items.append({'code': subnode.get('code'),
                          'name': subnode.get('name'),
                          'subcommittee': subnode.get('subcommittee'),
                          })

        comlist = []
        for x, item in enumerate(items):
            # If subcommittee then continue
            # because we already process it in previous step
            if item['subcommittee']:
                continue
            else:
                processed = False
                # Ok, current item is committee
                # If next item exists
                if x + 1 <= len(items) - 1:
                    # if next item is subcommittee
                    if items[x + 1]['subcommittee']:
                        # then save next item
                        processed = True
                        next_item = items[x + 1]
                        try:
                            com = Committee.objects.get(name=next_item['subcommittee'],
                                                        committee__code=item['code'])
                        except Committee.DoesNotExist:
                            log.error('Could not find subcommittee [name: %s, parent_code: %s]' % (next_item['subcommittee'], item['code']))
                        else:
                            comlist.append(com)
                if not processed:
                    # Next item is not subcommittee
                    # OR it is the last item in list
                    # Save current committee
                    try:
                        com = Committee.objects.get(code=item['code'])
                    except Committee.DoesNotExist:
                        log.error('Could not find committee [code: %s]' % item['code'])
                    else:
                        comlist.append(com)
        obj.committees = comlist

    def process_terms(self, obj, node):
        termlist = []
        for subnode in node.xpath('./subjects/term'):
            name = subnode.get('name')
            try:
                termlist.extend(get_term(name))
            except KeyError:
                log.error('Could not find term [name: %s]' % name)
        obj.terms = termlist



def main(options):
    """
    Process bill terms
    """

    term_processor = TermProcessor()
    BillTerm.objects.all().delete()

    log.info('Processing old bill terms')
    TERMS_FILE = 'data/us/liv.xml'
    tree = etree.parse(TERMS_FILE)
    for node in tree.xpath('/liv/top-term'):
        term = term_processor.process(BillTerm(), node)
        term.term_type = TermType.old
        term.save()

        for subnode in node.xpath('./term'):
            subterm = term_processor.process(BillTerm(), subnode)
            subterm.parent = term
            subterm.term_type = TermType.old
            try:
                subterm.save()
            except IntegrityError:
                log.error('Duplicated term %s' % term_processor.display_node(subnode))

    log.info('Processing new bill terms')
    for FILE in ('data/us/liv111.xml', 'data/us/crsnet.xml'):
        tree = etree.parse(FILE)
        for node in tree.xpath('/liv/top-term'):
            term = term_processor.process(BillTerm(), node)
            term.term_type = TermType.new
            term.save()

            for subnode in node.xpath('./term'):
                subterm = term_processor.process(BillTerm(), subnode)
                subterm.parent = term
                subterm.term_type = TermType.new
                try:
                    subterm.save()
                except IntegrityError:
                    log.error('Duplicated term %s' % term_processor.display_node(subnode))


def main(options):
    log.info('Processing bills')
    bill_processor = BillProcessor()
    Bill.objects.all().delete()
    for fname in glob.glob('data/us/112/bills/*.xml'):
        print fname
        tree = etree.parse(fname)
        for node in tree.xpath('/bill'):
            bill = bill_processor.process(Bill(), node)
            bill.save()


if __name__ == '__main__':
    main()
