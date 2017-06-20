#!script
"""
Parser of:
 * bill terms located in data/us/[liv, liv111, crsnet].xml
 * bills located in data/us/*/bills/*.xml
 
for x in {82..112}; do echo $x; ./parse.py bill --congress=$x -l ERROR --force --disable-events --disable-indexing; done
"""
from lxml import etree
import logging
from django.db.utils import IntegrityError
import glob
import re
import time
import urllib
import os.path
import json
from datetime import datetime, timedelta, date

from parser.progress import Progress
from parser.processor import XmlProcessor
from parser.models import File
from bill.models import BillTerm, TermType, BillType, Bill, Cosponsor, BillStatus, RelatedBill
from person.models import Person
from bill.title import get_primary_bill_title
from bill.billtext import get_bill_text_metadata
from committee.models import Committee
from settings import CURRENT_CONGRESS

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
            if term.term_type == TermType.new and term.is_top_term():
                # use top terms in old bills, these are new Policy Area Terms applied
                # even to pre-111th Congress bills.
                TERM_CACHE[(TermType.old, normalize_name(term.name))] = term
        # Re-use the new named entities terms for pre-111th Congress bill.s
        for term in BillTerm.objects.get(name="Geographic Areas, Entities, and Committees").subterms.all():
                TERM_CACHE[(TermType.old, normalize_name(term.name))] = term
            
    return TERM_CACHE[(TermType.new if congress >= 111 else TermType.old, normalize_name(name))]

class TermProcessor(XmlProcessor):
    REQUIRED_ATTRIBUTES = ['value']
    ATTRIBUTES = ['value']
    FIELD_MAPPING = {'value': 'name'}
    

class BillProcessor(XmlProcessor):
    REQUIRED_ATTRIBUTES = ['type', 'session', 'number']
    ATTRIBUTES = ['type', 'session', 'number']
    FIELD_MAPPING = {'type': 'bill_type', 'session': 'congress'}

    def type_handler(self, value):
        return BillType.by_xml_code(value)

    def process(self, obj, node):
        obj = super(BillProcessor, self).process(obj, node)

        # update existing bill record if one exists, otherwise create a new one on save()
        try:
            existing_bill_obj = Bill.objects.get(congress=obj.congress, bill_type=obj.bill_type, number=obj.number)
            obj.id = existing_bill_obj.id

            # if lock_title is set on the old record, pull its title forward and keep it locked
            if existing_bill_obj.lock_title:
                obj.title = existing_bill_obj.title
                obj.lock_title = existing_bill_obj.lock_title

            # pull forward other fields set on the Bill object that don't
            # come from the bill status XML
            obj.text_incorporation = existing_bill_obj.text_incorporation
        except Bill.DoesNotExist:
            pass

        self.process_titles(obj, node)
        self.process_introduced(obj, node)
        self.process_sponsor(obj, node)
        self.process_current_status(obj, node)

        # set source flag
        if obj.congress >= 93:
            obj.source = "thomas-congproj"
        elif obj.congress >= 82:
            obj.source = "statutesatlarge"
            if obj.current_status == BillStatus.enacted_signed: obj.current_status = BillStatus.enacted_unknown
        elif obj.congress <= 42:
            obj.source = "americanmemory"
        else:
            raise ValueError()

        obj.save() # save before using m2m relations
        self.process_committees(obj, node)
        if int(obj.congress) >= 93:
            # Bills from the Statutes at Large use some other subject term domain.
            self.process_terms(obj, node, obj.congress)
        self.process_consponsors(obj, node)
        self.process_relatedbills(obj, node)
        self.process_committee_reports(obj, node)
        return obj

    def process_introduced(self, obj, node):
        elem = node.xpath('./introduced')[0]
        obj.introduced_date = self.parse_datetime(elem.get('datetime')).date()

    def process_current_status(self, obj, node):
        elem = node.xpath('./state')[0]
        status = elem.text
        if status == "REFERRED": status = "INTRODUCED"
        obj.current_status_date = self.parse_datetime(elem.get('datetime'))
        obj.current_status = BillStatus.by_xml_code(status)

    def process_titles(self, obj, node):
        titles = []
        for elem in node.xpath('./titles/title'):
            text = unicode(elem.text) if elem.text else None
            titles.append((elem.get('type') + ("-partial" if elem.get("partial") == "1" else ""), elem.get('as'), text))
        obj.titles = titles
        
        # let the XML override the displayed bill number (American Memory bills)
        n = unicode(node.xpath('string(bill-number)'))
        if not n: n = None
        
        if not obj.lock_title:
            obj.title = get_primary_bill_title(obj, titles, override_number=n)[0:254]

    def process_sponsor(self, obj, node):
        try:
            obj.sponsor = get_person(node.xpath('./sponsor')[0].get('id'))
            obj.sponsor_role = obj.sponsor.get_role_at_date(obj.introduced_date)
        except IndexError: # no sponsor node
            obj.sponsor = None
        except TypeError: # no id attribute
            obj.sponsor = None

    def process_consponsors(self, obj, node):
        cosp = set()
        for subnode in node.xpath('./cosponsors/cosponsor'):
            try:
                person = get_person(subnode.get('id'))
            except IndexError:
                log.error('Could not find cosponsor %s' % subnode.get('id'))
            else:
                joined = self.parse_datetime(subnode.get('joined'))
                
                role = Cosponsor.get_role_for(person, obj, joined)
                if not role:
                    log.error('Cosponsor %s did not have a role on %s' % (unicode(person).encode("utf8"), subnode.get('joined')))
                    continue

                value = subnode.get('withdrawn')
                withdrawn = self.parse_datetime(value) if value else None
                
                ob, isnew = Cosponsor.objects.get_or_create(
                    person=person,
                    bill=obj,
                    defaults={
                        "joined": joined,
                        "withdrawn": withdrawn,
                        "role": role
                    })
                if ob.joined != joined or ob.withdrawn != withdrawn or ob.role != role:
                    ob.joined = joined
                    ob.withdrawn = withdrawn
                    ob.role = role
                    ob.save()
                cosp.add(ob.id)

        obsolete_cosp = Cosponsor.objects.filter(bill=obj).exclude(id__in=cosp)
        if obsolete_cosp.count() > 0:
            log.error('Deleting obsolete cosponsor records: %s' % obsolete_cosp)
            obsolete_cosp.delete()
           

    def session_handler(self, value):
        return int(value)

    def number_handler(self, value):
        return int(value)

    def process_committees(self, obj, node):
        comlist = []
        for subnode in node.xpath('./committees/committee'):
            if subnode.get('code') in ("", None):
                if obj.congress >= 93:
                    log.warn("Missing code attribute on committee %s." % subnode.get("name"))
                continue
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
            RelatedBill.objects.create(bill=obj, related_bill=related_bill, relation=subnode.get("relation")[0:16])
                    
    def process_committee_reports(self, obj, node):
        obj.committee_reports = [
            subnode.text
            for subnode in node.xpath('./committee-reports/report')]


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
        existing_terms[(int(term.term_type), term.name)] = term

    log.info('Processing old bill terms')
    TERMS_FILE = 'data/us/liv.xml'
    tree = etree.parse(TERMS_FILE)
    for node in tree.xpath('/liv/top-term'):
        term = term_processor.process(BillTerm(), node)
        term.term_type = TermType.old
        try:
            # No need to update an existing term because there are no other attributes.
            term = existing_terms[(int(term.term_type), term.name)]
            terms_parsed.add(term.id)
        except:
            log.debug("Created %s" % term)
            term.save()
            term.subterms.clear()
            
        for subnode in node.xpath('./term'):
            subterm = term_processor.process(BillTerm(), subnode)
            subterm.term_type = TermType.old
            try:
                # No need to update an existing term because there are no other attributes.
                subterm = existing_terms[(int(subterm.term_type), subterm.name)]
                term.subterms.add(subterm) 
                terms_parsed.add(subterm.id)
            except:
                try:
                    log.debug("Created %s" % subterm)
                    subterm.save()
                    term.subterms.add(subterm)
                    
                    existing_terms[(int(subterm.term_type), subterm.name)] = subterm
                    terms_parsed.add(subterm.id)
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
                term = existing_terms[(int(term.term_type), term.name)]
                terms_parsed.add(term.id)
            except:
                log.debug("Created %s" % term)
                term.save()
                term.subterms.clear()

            for subnode in node.xpath('./term'):
                subterm = term_processor.process(BillTerm(), subnode)
                subterm.term_type = TermType.new
                try:
                    # No need to update an existing term because there are no other attributes.
                    subterm = existing_terms[(int(subterm.term_type), subterm.name)]
                    terms_parsed.add(subterm.id)
                    term.subterms.add(subterm)
                except:
                    try:
                        log.debug("Created %s" % term)
                        subterm.save()
                        term.subterms.add(subterm)
                        
                        existing_terms[(int(subterm.term_type), subterm.name)] = subterm
                        terms_parsed.add(subterm.id)
                    except IntegrityError:
                        log.error('Duplicated term %s' % term_processor.display_node(subnode))

    for term in existing_terms.values():
        if not term.id in terms_parsed:
            log.debug("Deleted %s" % term)
            term.delete()

    # Bills
    
    bill_index = None
    if not options.disable_indexing:
        from bill.search_indexes import BillIndex
        bill_index = BillIndex()

    if options.congress and int(options.congress) <= 42:
        files = glob.glob('data/congress/%s/bills/*/*/*.xml' % options.congress)
        log.info('Parsing unitedstates/congress bills of only congress#%s' % options.congress)
    elif options.congress:
        files = glob.glob('data/us/%s/bills/*.xml' % options.congress)
        log.info('Parsing bills of only congress#%s' % options.congress)
    else:
        files = glob.glob('data/us/*/bills/*.xml')
        
    if options.filter:
        files = [f for f in files if re.match(options.filter, f)]
        
    log.info('Processing bills: %d files' % len(files))
    total = len(files)
    progress = Progress(total=total, name='files', step=100)

    bill_processor = BillProcessor()
    seen_bill_ids = []
    for fname in files:
        progress.tick()
        
        # With indexing or events enabled, if the bill metadata file hasn't changed check
        # the bill's latest text file for changes so we can create a text-is-available
        # event and so we can index the bill's text.
        if (not options.congress or options.congress>42) and (bill_index and not options.disable_events) and not File.objects.is_changed(fname) and not options.force:
            m = re.search(r"/(\d+)/bills/([a-z]+)(\d+)\.xml$", fname)

            try:
                b = Bill.objects.get(congress=m.group(1), bill_type=BillType.by_xml_code(m.group(2)), number=m.group(3))
                seen_bill_ids.append(b.id)
                
                # Update the index/events for any bill with recently changed text
                textfile = get_bill_text_metadata(b, None)
                if not textfile:
                    if b.congress >= 103 and b.introduced_date < (datetime.now()-timedelta(days=14)).date():
                        print "No bill text?", fname, b.introduced_date
                    continue
                textfile = textfile["text_file"]
                if os.path.exists(textfile) and File.objects.is_changed(textfile):
                    b.update_index(bill_index) # index the full text
                    b.create_events() # events for new bill text documents
                    File.objects.save_file(textfile)
                    
                continue
            except Bill.DoesNotExist:
                print "Unchanged metadata file but bill doesn't exist:", fname
                pass # just parse as normal
            
        if options.slow:
            time.sleep(1)
            
        tree = etree.parse(fname)
        for node in tree.xpath('/bill'):
            try:
                bill = bill_processor.process(Bill(), node)
            except:
                print fname
                raise
           
            seen_bill_ids.append(bill.id) # don't delete me later
            
            # So far this is just for American Memory bills.
            if node.xpath("string(source/@url)"):
                bill.source_link = unicode(node.xpath("string(source/@url)"))
            else:
                bill.source_link = None

            actions = []
            for axn in tree.xpath("actions/*[@state]"):
                if axn.xpath("string(@state)") == "REFERRED": continue # we don't track this state
                actions.append( (
                	repr(bill_processor.parse_datetime(axn.xpath("string(@datetime)"))),
                	BillStatus.by_xml_code(axn.xpath("string(@state)")),
                	axn.xpath("string(text)"),
                    etree.tostring(axn),
                	) )
                
            bill.sliplawpubpriv = None
            bill.sliplawnum = None
            for axn in tree.xpath("actions/enacted"):
                bill.sliplawpubpriv = "PUB" if axn.get("type") == "public" else "PRI"
                bill.sliplawnum = int(axn.get("number").split("-")[1])
                    
            bill.major_actions = actions
            try:
                bill.save()
            except:
                print bill
                raise

            if bill_index:
                bill.update_index(bill_index)

            if not options.disable_events:
                bill.create_events()
                
        File.objects.save_file(fname)
        
    # delete bill objects that are no longer represented on disk.... this is too dangerous.
    if options.congress and not options.filter:
        # this doesn't work because seen_bill_ids is too big for sqlite!
        for b in Bill.objects.filter(congress=options.congress).exclude(id__in = seen_bill_ids):
            print "Bill is no longer on disk: ", b.id, b
        
    # The rest is for current only...
    
    if options.congress and int(options.congress) != CURRENT_CONGRESS:
        return
        
    # Find what might be coming up this week.
    load_docs_house_gov(options, bill_index)
    load_senate_floor_schedule(options, bill_index)


def load_senate_floor_schedule(options, bill_index):
    now = datetime.now()
    for entry in load_senate_floor_schedule_data():
        if entry["date"] >= now.date():
            bill = Bill.objects.get(congress=entry["bill_congress"], bill_type=entry["bill_type"], number=entry["bill_number"])
            if bill.senate_floor_schedule_postdate == None or now - bill.senate_floor_schedule_postdate > timedelta(days=7):
                bill.senate_floor_schedule_postdate = now
                if bill.docs_house_gov_postdate is None or bill.senate_floor_schedule_postdate > bill.docs_house_gov_postdate: bill.scheduled_consideration_date = entry["date"]
                bill.save()
                if bill_index:
                    bill.update_index(bill_index)
                if not options.disable_events:
                    bill.create_events()

def load_senate_floor_schedule_data():
    try:
        dom = etree.parse(urllib.urlopen("https://www.senate.gov/legislative/schedule/floor_schedule.xml")).getroot()
    except etree.XMLSyntaxError:
        print "Invalid XML received for https://www.senate.gov/legislative/schedule/floor_schedule.xml"
        return
    def get(node, key): return node.find(key).text
    year = int(get(dom, "year"))
    congress = int(get(dom, "congress"))
    for meeting in dom.findall("meeting/convene"):
        d = date(year, int(meeting.get("month")), int(meeting.get("date")))
        for measure in \
           [meeting.get("measure")] \
           + [m.text for m in meeting.findall("full_text/measure")]:
            if not measure: continue # empty measure attribute
            bill_type, bill_number = re.match(r"(\w+?)(\d+)$", measure).groups()
            bill_type_map = {
              "s": BillType.senate_bill,
              "se": BillType.senate_resolution,
              "sj": BillType.senate_joint_resolution,
              "sc": BillType.senate_concurrent_resolution,
              "h": BillType.house_bill,
              "hj": BillType.house_joint_resolution,
              "hc": BillType.house_concurrent_resolution,
            }
            measure = bill_type + "|" + bill_number
            yield {
                "date": d,
                "bill_congress": congress,
                "bill_type": bill_type_map[bill_type],
                "bill_number": bill_number,
            }

def load_docs_house_gov(options, bill_index):
    # Look at the three most recent JSON files by looking at the lexicographically last ones,
    # which possibly cover the current week, the next week, and the week after that.
    for fn in sorted(os.listdir("data/congress/upcoming_house_floor"))[-3:]:
        data = json.load(open("data/congress/upcoming_house_floor/" + fn))
        for billinfo in data.get("upcoming", []):
            if "bill_id" not in billinfo: continue
    
            m = re.match(r"([hrsjconres]+)(\d+)-(\d+)", billinfo["bill_id"])
            if not m:
                log.error('Could not parse bill_id "%s" in docs.house.gov.' % billinfo["bill_id"])
                continue
 
            bt = BillType.by_slug(m.group(1))
            try:
                bill = Bill.objects.get(congress=int(m.group(3)), bill_type=bt, number=int(m.group(2)))
            except Exception as e:
                log.error('Could not get bill "%s" in docs.house.gov: %s.' % (billinfo["bill_id"], str(e)))
                continue

            bill.docs_house_gov_postdate = BillProcessor.parse_datetime(billinfo["published_at"])
            if bill.senate_floor_schedule_postdate is None or bill.docs_house_gov_postdate > bill.senate_floor_schedule_postdate: bill.scheduled_consideration_date = BillProcessor.parse_datetime(data["week_of"])
            bill.save()
            if bill_index: bill.update_index(bill_index)
            if not options.disable_events: bill.create_events()

if __name__ == '__main__':
    import pprint
    pprint.pprint(list(load_senate_floor_schedule_data()))
