"""
Parse bills related data.
"""
from lxml import etree
import logging
from django.db.utils import IntegrityError
import glob

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from bill.models import BillTerm, TermType, BillType, Bill
from person.models import Person
from bill.title import get_bill_title

log = logging.getLogger('parser.bill_parser')
PERSON_CACHE = {}

def get_person(pk):
    global PERSON_CACHE
    if not PERSON_CACHE:
        PERSON_CACHE = dict((x.pk, x) for x in Person.objects.all())
    return PERSON_CACHE[pk]


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
        try:
            obj.sponsor = get_person(node.xpath('./person')[0].get('id'))
        except IndexError:
            obj.sponsor = None
        return obj

    def process_titles(self, obj, node):
        titles = []
        for elem in node.xpath('./titles/title'):
            text = unicode(elem.text) if elem.text else None
            titles.append((elem.get('type'), elem.get('as'), text))
        obj.titles = titles
        obj.title = get_bill_title(obj, titles, 'short')

    def session_handler(self, value):
        return int(value)


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
