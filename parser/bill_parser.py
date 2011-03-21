"""
Parse bills related data.
"""
from lxml import etree
import logging
from django.db.utils import IntegrityError

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from bill.models import BillTerm, TermType

log = logging.getLogger('parser.bill_parser')

class TermProcessor(Processor):
    REQUIRED_ATTRIBUTES = ['value']
    ATTRIBUTES = ['value']
    FIELD_MAPPING = {'value': 'name'}


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


if __name__ == '__main__':
    main()
