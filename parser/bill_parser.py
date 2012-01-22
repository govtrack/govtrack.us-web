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
from bill.models import BillTerm, TermType, BillType, Bill, Cosponsor, BillStatus, RelatedBill
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


def get_term(name, congress):
    global TERM_CACHE
    if not TERM_CACHE:
        for term in BillTerm.objects.all():
            TERM_CACHE[(term.term_type, normalize_name(term.name))] = term
    return TERM_CACHE[(TermType.new if congress >= 111 else TermType.old, normalize_name(name))]

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

        # update existing bill record if one exists, otherwise create a new one on save()
        try:
            obj.id = Bill.objects.get(congress=obj.congress, bill_type=obj.bill_type, number=obj.number).id
        except Bill.DoesNotExist:
            pass
            
        obj.save() # save before using m2m relations
        self.process_committees(obj, node)
        self.process_terms(obj, node, obj.congress)
        self.process_consponsors(obj, node)
        self.process_relatedbills(obj, node)
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
        except IndexError: # no sponsor node
            obj.sponsor = None
        except TypeError: # no id attribute
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
                ob, isnew = Cosponsor.objects.get_or_create(person=person, bill=obj, defaults={"joined": joined, "withdrawn": withdrawn})
                if ob.joined != joined or ob.withdrawn != withdrawn:
                    ob.joined = joined
                    ob.withdrawn = withdrawn
                    ob.save()

    def session_handler(self, value):
        return int(value)

    def process_committees(self, obj, node):
        comlist = []
        for subnode in node.xpath('./committees/committee'):
            if subnode.get('code') == "": continue
            try:
                com = Committee.objects.get(code=subnode.get('code'))
            except Committee.DoesNotExist:
                log.error('Could not find committee %s' % subnode.get('code'))
            else:
                comlist.append(com)
        obj.committees = comlist

    def process_terms(self, obj, node, congress):
        termlist = []
        for subnode in node.xpath('./subjects/term'):
            name = subnode.get('name')
            try:
                termlist.append(get_term(name, congress))
            except KeyError:
                log.error('Could not find term [name: %s]' % name)
        obj.terms = termlist

    def process_relatedbills(self, obj, node):
        RelatedBill.objects.filter(bill=obj).delete()
        for subnode in node.xpath('./relatedbills/bill'):
            try:
                related_bill = Bill.objects.get(congress=subnode.get("session"), bill_type=BillType.by_xml_code(subnode.get("type")), number=int(subnode.get("number")))
            except Bill.DoesNotExist:
                continue
            RelatedBill.objects.create(bill=obj, related_bill=related_bill, relation=subnode.get("relation"))
                    


def main(options):
    """
    Process bill terms and bills
    """

    # Terms

    term_processor = TermProcessor()
    terms_parsed = set()
    
    # Cache existing terms. There aren't so many.
    existing_terms = { }
    for term in BillTerm.objects.all():
        existing_terms[(term.term_type, term.parent.id if term.parent else None, term.name)] = term.id

    log.info('Processing old bill terms')
    TERMS_FILE = 'data/us/liv.xml'
    tree = etree.parse(TERMS_FILE)
    for node in tree.xpath('/liv/top-term'):
        term = term_processor.process(BillTerm(), node)
        term.term_type = TermType.old
        try:
            # No need to update an existing term because there are no other attributes.
            term.id = existing_terms[(int(term.term_type), None, term.name)]
            terms_parsed.add(term.id)
        except:
            log.debug("Created %s" % term)
            term.save()

        for subnode in node.xpath('./term'):
            subterm = term_processor.process(BillTerm(), subnode)
            subterm.parent = term
            subterm.term_type = TermType.old
            try:
                # No need to update an existing term because there are no other attributes.
                subterm.id = existing_terms[(int(subterm.term_type), subterm.parent.id, subterm.name)]
                terms_parsed.add(subterm.id)
            except:
                try:
                    log.debug("Created %s" % subterm)
                    subterm.save()
                except IntegrityError:
                    log.error('Duplicated term %s' % term_processor.display_node(subnode))

    log.info('Processing new bill terms')
    for FILE in ('data/us/liv111.xml', 'data/us/crsnet.xml'):
        tree = etree.parse(FILE)
        for node in tree.xpath('/liv/top-term'):
            term = term_processor.process(BillTerm(), node)
            term.term_type = TermType.new
            try:
                # No need to update an existing term because there are no other attributes.
                term.id = existing_terms[(int(term.term_type), None, term.name)]
                terms_parsed.add(term.id)
            except:
                log.debug("Created %s" % term)
                term.save()

            for subnode in node.xpath('./term'):
                subterm = term_processor.process(BillTerm(), subnode)
                subterm.parent = term
                subterm.term_type = TermType.new
                try:
                    # No need to update an existing term because there are no other attributes.
                    subterm.id = existing_terms[(int(subterm.term_type), subterm.parent.id, subterm.name)]
                    terms_parsed.add(subterm.id)
                except:
                    try:
                        log.debug("Created %s" % term)
                        subterm.save()
                    except IntegrityError:
                        log.error('Duplicated term %s' % term_processor.display_node(subnode))

    for termid in existing_terms.values():
        if not termid in terms_parsed:
            term = BillTerm.objects.get(id=termid)
            log.debug("Deleted %s" % term)
            term.delete()

    # Bills

    if options.congress:
        files = glob.glob('data/us/%s/bills/*.xml' % options.congress)
        log.info('Parsing bills of only congress#%s' % options.congress)
    else:
        files = glob.glob('data/us/*/bills/*.xml')
    log.info('Processing bills: %d files' % len(files))
    total = len(files)
    progress = Progress(total=total, name='files', step=10)

    bill_processor = BillProcessor()
    seen_bill_ids = []
    for fname in files:
        progress.tick()
        
        if not File.objects.is_changed(fname) and not options.force:
            m = re.search(r"/(\d+)/bills/([a-z]+)(\d+)\.xml$", fname)
            seen_bill_ids.append(Bill.objects.get(congress=m.group(1), bill_type=BillType.by_xml_code(m.group(2)), number=m.group(3)).id)
            continue
            
        tree = etree.parse(fname)
        for node in tree.xpath('/bill'):
            bill = bill_processor.process(Bill(), node)
           
            seen_bill_ids.append(bill.id) # don't delete me later
            
            actions = []
            for axn in tree.xpath("actions/*[@state]"):
                actions.append( (bill_processor.parse_datetime(axn.xpath("string(@datetime)")), BillStatus.by_xml_code(axn.xpath("string(@state)")), axn.xpath("string(text)")) )
            
            bill.create_events(actions)

        File.objects.save_file(fname)

    # delete bill objects that are no longer represented on disk
    if options.congress:
        # this doesn't work because seen_bill_ids is too big for sqlite!
        Bill.objects.filter(congress=options.congress).exclude(id__in = seen_bill_ids).delete()

if __name__ == '__main__':
    main()
