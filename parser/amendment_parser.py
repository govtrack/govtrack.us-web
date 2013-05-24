"""
Parser for amendments.
 
for x in {82..112}; do echo $x; RELEASE=1 ./parse.py amendment --congress=$x -l ERROR --force --disable-events --disable-indexing; done
"""
from lxml import etree
import logging
from django.db.utils import IntegrityError
import glob
import re
import time
import urllib
import os.path
from datetime import datetime, timedelta

from parser.progress import Progress
from parser.processor import XmlProcessor
from parser.models import File
from bill.models import Amendment, AmendmentType, Bill, BillType
from person.models import Person
from settings import CURRENT_CONGRESS

log = logging.getLogger('parser.bill_parser')
PERSON_CACHE = {}

def get_person(pk):
    global PERSON_CACHE
    pk = int(pk)
    if not PERSON_CACHE:
        PERSON_CACHE = dict((x.pk, x) for x in Person.objects.all())
    return PERSON_CACHE[pk]

class AmendmentProcessor(XmlProcessor):
    REQUIRED_ATTRIBUTES = ['session', 'chamber', 'number']
    ATTRIBUTES = ['session', 'chamber', 'number']
    FIELD_MAPPING = {'chamber': 'amendment_type', 'session': 'congress'}

    def process(self, obj, node):
        obj = super(AmendmentProcessor, self).process(obj, node)
        self.process_offered(obj, node)
        self.process_sponsor(obj, node)
        self.process_bill(obj, node)
        self.process_title(obj, node)
        return obj

    def process_offered(self, obj, node):
        elem = node.xpath('offered')[0]
        obj.offered_date = self.parse_datetime(elem.get('datetime')).date()

    def process_title(self, obj, node):
        obj.title = \
             obj.get_amendment_type_display() + " " + str(obj.number) \
             + ((" (" + obj.sponsor.lastname + ")") if obj.sponsor else "") \
             + " to " + obj.bill.display_number
             
        for elem in node.xpath('description|purpose'):
            text = unicode(elem.text) if elem.text else ""
            if text.strip() != "":
                # Clean titles.
                text = re.sub(r"^(?:An )?(?:substitute )?amendment (?:in the nature of a substitute )?numbered (\d+) printed in (part .* of )?(House Report \d+-\d+|the Congressional Record) to ", "To ", text, re.I)
                obj.title += ": " + text
                break

    def process_sponsor(self, obj, node):
        try:
            obj.sponsor = get_person(node.xpath('sponsor')[0].get('id'))
            obj.sponsor_role = obj.sponsor.get_role_at_date(obj.offered_date)
        except IndexError: # no sponsor node
            obj.sponsor = None
        except TypeError: # no id attribute
            obj.sponsor = None

    def session_handler(self, value):
        return int(value)

    def chamber_handler(self, value):
        return AmendmentType.by_slug(value)

    def number_handler(self, value):
        return int(value)

    def process_bill(self, obj, node):
        amends_type = BillType.by_xml_code(node.xpath('string(amends/@type)'))
        amends_number = int(node.xpath('string(amends/@number)'))
        try:
            amends_seq = int(node.xpath('string(amends/@sequence)'))
        except ValueError:
            amends_seq = None
        obj.bill = Bill.objects.get(congress=obj.congress, bill_type=amends_type, number=amends_number)
        obj.sequence = amends_seq

def main(options):
    """
    Process amendments
    """

    if options.congress:
        files = glob.glob('data/us/%s/bills.amdt/*.xml' % options.congress)
        log.info('Parsing amendments of only congress#%s' % options.congress)
    else:
        files = glob.glob('data/us/*/bills.amdt/*.xml')
        
    if options.filter:
        files = [f for f in files if re.match(options.filter, f)]
        
    log.info('Processing amendments: %d files' % len(files))
    total = len(files)
    progress = Progress(total=total, name='files', step=100)

    amendment_processor = AmendmentProcessor()
    seen_amdt_ids = []
    for fname in files:
        progress.tick()
        
        if not File.objects.is_changed(fname) and not options.force:
            continue
            
        tree = etree.parse(fname)
        node = tree.xpath('/amendment')[0]
        
        try:
            amdt = amendment_processor.process(Amendment(), node)
        except:
            print fname
            raise
            
        # update if already in db
        try:
            amdt.id = Amendment.objects.get(congress=amdt.congress, amendment_type=amdt.amendment_type, number=amdt.number).id
        except Amendment.DoesNotExist:
            pass # a new amendment
       
        seen_amdt_ids.append(amdt.id) # don't delete me later
        
        try:
            amdt.save()
        except:
            print amdt
            raise

        File.objects.save_file(fname)
        
    # delete bill objects that are no longer represented on disk.... this is too dangerous.
    if options.congress and not options.filter and False:
        # this doesn't work because seen_bill_ids is too big for sqlite!
        Amendment.objects.filter(congress=options.congress).exclude(id__in = seen_amdt_ids).delete()


if __name__ == '__main__':
    main()
