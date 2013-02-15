"""
Parse list of committees which ever were in Congress.
Parse members of current congress committees.
"""
from lxml import etree
from datetime import datetime
import logging

from parser.progress import Progress
from parser.processor import XmlProcessor
from parser.processor import YamlProcessor, yaml_load
from parser.models import File
from committee.models import (Committee, CommitteeType, CommitteeMember,
                              CommitteeMemberRole, CommitteeMeeting)
from person.models import Person
from bill.models import Bill, BillType

log = logging.getLogger('parser.committee_parser')

TYPE_MAPPING = {'senate': CommitteeType.senate,
                'joint': CommitteeType.joint,
                'house': CommitteeType.house}

ROLE_MAPPING = {
    'Ex Officio': CommitteeMemberRole.exofficio,
    'Chairman': CommitteeMemberRole.chairman,
    'Cochairman': CommitteeMemberRole.chairman, # huh!
    'Chair': CommitteeMemberRole.chairman,
    'Ranking Member': CommitteeMemberRole.ranking_member,
    'Vice Chairman': CommitteeMemberRole.vice_chairman,
    'Vice Chair': CommitteeMemberRole.vice_chairman,
    'Vice Chairwoman': CommitteeMemberRole.vice_chairman,
    'Member': CommitteeMemberRole.member,
}

class CommitteeMeetingProcessor(XmlProcessor):
    """
    Parser of committeeschedule.xml.
    """

    REQUIRED_ATTRIBUTES = ['committee-id', 'datetime']
    ATTRIBUTES = ['committee-id', 'datetime']
    REQUIRED_NODES = ['subject']
    NODES = ['subject']
    FIELD_MAPPING = {'committee-id': 'committee', 'datetime': 'when'}

    def committee_id_handler(self, value):
        return Committee.objects.get(code=value)

    def datetime_handler(self, value):
        return self.parse_datetime(value)


def main(options):
    """
    Process committees, subcommittees and
    members of current congress committees.
    """

    BASE_PATH = '../scripts/congress/cache/congress-legislators/'
    
    meeting_processor = CommitteeMeetingProcessor()

    log.info('Processing committees')
    COMMITTEES_FILE = BASE_PATH + 'committees-current.yaml'

    if not File.objects.is_changed(COMMITTEES_FILE) and not options.force:
        log.info('File %s was not changed' % COMMITTEES_FILE)
    else:
        tree = yaml_load(COMMITTEES_FILE)
        total = len(tree)
        progress = Progress(total=total)
        seen_committees = set()
        for committee in tree:
            try:
                cobj = Committee.objects.get(code=committee["thomas_id"])
            except Committee.DoesNotExist:
                print "New committee:", committee["thomas_id"]
                cobj = Committee(code=committee["thomas_id"])
               
            cobj.committee_type = TYPE_MAPPING[committee["type"]]
            cobj.name = committee["name"]
            cobj.url = committee.get("url", None)
            cobj.obsolete = False
            cobj.committee = None
            cobj.save()
            seen_committees.add(cobj.id)

            for subcom in committee.get('subcommittees', []):
                code = committee["thomas_id"] + subcom["thomas_id"]
                try:
                    sobj = Committee.objects.get(code=code)
                except Committee.DoesNotExist:
                    print "New subcommittee:", code
                    sobj = Committee(code=code)
                
                sobj.name = subcom["name"]
                sobj.url = subcom.get("url", None)
                sobj.type = None
                sobj.committee = cobj
                sobj.obsolete = False
                sobj.save()
                seen_committees.add(sobj.id)
                
            progress.tick()
            
        # Check for non-obsolete committees in the database that aren't in our
        # file.
        other_committees = Committee.objects.filter(obsolete=False).exclude(id__in=seen_committees)
        if len(other_committees) > 0:
            print "Marking obsolete:", ", ".join(c.code for c in other_committees)
            other_committees.update(obsolete=True)

        File.objects.save_file(COMMITTEES_FILE)
        
    log.info('Processing committee members')
    MEMBERS_FILE = BASE_PATH + 'committee-membership-current.yaml'
    file_changed = File.objects.is_changed(MEMBERS_FILE)

    if not file_changed and not options.force:
        log.info('File %s was not changed' % MEMBERS_FILE)
    else:
        # map THOMAS IDs to GovTrack IDs
        y = yaml_load(BASE_PATH + "legislators-current.yaml")
        person_id_map = { }
        for m in y:
            if "id" in m and "govtrack" in m["id"] and "thomas" in m["id"]:
                person_id_map[m["id"]["thomas"]] = m["id"]["govtrack"]
        
        # load committee members
        tree = yaml_load(MEMBERS_FILE)
        total = len(tree)
        progress = Progress(total=total, name='committees')
        
        # We can delete CommitteeMember objects because we don't have
        # any foreign keys to them.
        CommitteeMember.objects.all().delete()

        # Process committee nodes
        for committee, members in tree.items():
            if committee[0] == "H": continue # House data is out of date
            
            try:
                cobj = Committee.objects.get(code=committee)
            except Committee.DoesNotExist:
                print "Committee not found:", committee
                continue

            # Process members of current committee node
            for member in members:
                mobj = CommitteeMember()
                mobj.person = Person.objects.get(id=person_id_map[member["thomas"]])
                mobj.committee = cobj
                if "title" in member:
                    mobj.role = ROLE_MAPPING[member["title"]]
                mobj.save()
            
            progress.tick()

        File.objects.save_file(MEMBERS_FILE)
        
    return

    log.info('Processing committee schedule')
    SCHEDULE_FILE = 'data/us/112/committeeschedule.xml'
    file_changed = File.objects.is_changed(SCHEDULE_FILE)

    if not file_changed and not options.force:
        log.info('File %s was not changed' % SCHEDULE_FILE)
    else:
        tree = etree.parse(SCHEDULE_FILE)
        
        # We have to clear out all CommitteeMeeting objects when we refresh because
        # we have no unique identifier in the upstream data for a meeting. We might use
        # the meeting's committee & date as an identifier, but since meeting times can
        # change this might have awkward consequences for the end user if we even
        # attempted to track that.

        CommitteeMeeting.objects.all().delete()

        # Process committee event nodes
        for meeting in tree.xpath('/committee-schedule/meeting'):
            try:
                mobj = meeting_processor.process(CommitteeMeeting(), meeting)
                mobj.save()
                
                mobj.bills.clear()
                for bill in meeting.xpath('bill'):
                    bill = Bill.objects.get(congress=bill.get("session"), bill_type=BillType.by_xml_code(bill.get("type")), number=int(bill.get("number")))
                    mobj.bills.add(bill)
            except Committee.DoesNotExist:
                log.error('Could not load Committee object for meeting %s' % meeting_processor.display_node(meeting))

        for committee in Committee.objects.all():
            if not options.disable_events:
                committee.create_events()
            
        File.objects.save_file(SCHEDULE_FILE)
    

if __name__ == '__main__':
    main()
