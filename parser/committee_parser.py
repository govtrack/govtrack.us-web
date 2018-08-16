"""
Parse list of committees which ever were in Congress.
Parse members of current congress committees.
"""
from lxml import etree
from datetime import datetime
import logging

from django.conf import settings

from parser.progress import Progress
from parser.processor import YamlProcessor, yaml_load
from parser.models import File
from committee.models import (Committee, CommitteeType, CommitteeMember,
                              CommitteeMemberRole, CommitteeMeeting)
from person.models import Person
from bill.models import Bill, BillType

import json, re
import common.enum

log = logging.getLogger('parser.committee_parser')

TYPE_MAPPING = {'senate': CommitteeType.senate,
                'joint': CommitteeType.joint,
                'house': CommitteeType.house}

ROLE_MAPPING = {
    'Ex Officio': CommitteeMemberRole.exofficio,
    'Chairman': CommitteeMemberRole.chair,
    'Cochairman': CommitteeMemberRole.chair, # huh!
    'Co-Chairman': CommitteeMemberRole.chair, # huh!
    'Chair': CommitteeMemberRole.chair,
    'Ranking Member': CommitteeMemberRole.ranking_member,
    'Vice Chairman': CommitteeMemberRole.vice_chair,
    'Vice Chair': CommitteeMemberRole.vice_chair,
    'Vice Chairwoman': CommitteeMemberRole.vice_chair,
    'Member': CommitteeMemberRole.member,
}

class CommitteeMeetingProcessor(YamlProcessor):
    """
    Parser of committee meeting JSON files.
    """

    REQUIRED_ATTRIBUTES = ['committee', 'occurs_at', 'topic', 'guid']
    ATTRIBUTES = ['committee', 'subcommittee', 'occurs_at', 'topic', 'guid', 'room']
    FIELD_MAPPING = { 'occurs_at': 'when', 'topic': 'subject' }

    def committee_handler(self, value):
        return Committee.objects.get(code=value)

    def occurs_at_handler(self, value):
        return self.parse_datetime(value)


def main(options):
    """
    Process committees, subcommittees and
    members of current congress committees.
    """

    BASE_PATH = settings.CONGRESS_LEGISLATORS_PATH
    
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
                print("New committee:", committee["thomas_id"])
                cobj = Committee(code=committee["thomas_id"])
               
            cobj.committee_type = TYPE_MAPPING[committee["type"]]
            cobj.name = committee["name"]
            cobj.url = committee.get("url", None)
            cobj.obsolete = False
            cobj.committee = None
            cobj.jurisdiction = committee.get("jurisdiction")
            cobj.jurisdiction_link = committee.get("jurisdiction_source")
            cobj.save()
            seen_committees.add(cobj.id)

            for subcom in committee.get('subcommittees', []):
                code = committee["thomas_id"] + subcom["thomas_id"]
                try:
                    sobj = Committee.objects.get(code=code)
                except Committee.DoesNotExist:
                    print("New subcommittee:", code)
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
            print("Marking obsolete:", ", ".join(c.code for c in other_committees))
            other_committees.update(obsolete=True)

        File.objects.save_file(COMMITTEES_FILE)
        
    log.info('Processing committee members')
    MEMBERS_FILE = BASE_PATH + 'committee-membership-current.yaml'
    file_changed = File.objects.is_changed(MEMBERS_FILE)

    if not file_changed and not options.force:
        log.info('File %s was not changed' % MEMBERS_FILE)
    else:
        # map Bioguide IDs to GovTrack IDs
        y = yaml_load(BASE_PATH + "legislators-current.yaml")
        person_id_map = { }
        for m in y:
            if "id" in m and "govtrack" in m["id"] and "bioguide" in m["id"]:
                person_id_map[m["id"]["bioguide"]] = m["id"]["govtrack"]
        
        # load committee members
        tree = yaml_load(MEMBERS_FILE)
        total = len(tree)
        progress = Progress(total=total, name='committees')
        
        # We can delete CommitteeMember objects because we don't have
        # any foreign keys to them.
        CommitteeMember.objects.all().delete()

        # Process committee nodes
        for committee, members in tree.items():
            try:
                cobj = Committee.objects.get(code=committee)
            except Committee.DoesNotExist:
                print("Committee not found:", committee)
                continue

            # Process members of current committee node
            for member in members:
                mobj = CommitteeMember()
                mobj.person = Person.objects.get(id=person_id_map[member["bioguide"]])
                mobj.committee = cobj
                if "title" in member:
                    mobj.role = ROLE_MAPPING[member["title"]]
                mobj.save()
            
            progress.tick()

        File.objects.save_file(MEMBERS_FILE)
        
    log.info('Processing committee schedule')
    loaded_meetings = set()
    processed_all_meetings = True
    for chamber in ("house", "senate"):
    	meetings_file = 'data/congress/committee_meetings_%s.json' % chamber
    	file_changed = File.objects.is_changed(meetings_file)
    
    	if not file_changed and not options.force:
    		log.info('File %s was not changed' % meetings_file)
    		processed_all_meetings = False
    	else:
    		meetings = json.load(open(meetings_file))
    		
    		# Process committee event nodes
    		for meeting in meetings:
    			try:
    				# Associate it with an existing meeting object if GUID is already known.
    				# Must get it like this, vs just assigning the ID as we do in other parsers,
    				# because of the auto_now_add created field, which otherwise misbehaves.
    				try:
    					mobj = CommitteeMeeting.objects.get(guid=meeting['guid'])
    				except CommitteeMeeting.DoesNotExist:
    					mobj = CommitteeMeeting()
    				
    				# Parse.
    				mobj = meeting_processor.process(mobj, meeting)
    				
    				# Attach the meeting to the subcommittee if set.
    				if mobj.subcommittee:
    					mobj.committee = Committee.objects.get(code=mobj.committee.code + mobj.subcommittee)
    				
    				mobj.save()
    				loaded_meetings.add(mobj.id)
    				
    				mobj.bills.clear()
    				for bill in meeting["bill_ids"]:
    				    try:
    				        bill_type, bill_num, bill_cong = re.match(r"([a-z]+)(\d+)-(\d+)$", bill).groups()
    				        bill = Bill.objects.get(congress=bill_cong, bill_type=BillType.by_slug(bill_type), number=int(bill_num))
    				        mobj.bills.add(bill)
    				    except AttributeError:
    				        pass # regex failed
    				    except common.enum.NotFound:
    				        pass # invalid bill type code in source data
    				    except Bill.DoesNotExist:
    				        pass # we don't know about bill yet
    			except Committee.DoesNotExist:
    				log.error('Could not load Committee object for meeting %s' % meeting_processor.display_node(meeting))
    
    		File.objects.save_file(meetings_file)
    	
    if processed_all_meetings:
        # Drop any future meetings that are no longer in the source data.
        obsolete_mtgs = CommitteeMeeting.objects.exclude(id__in=loaded_meetings).filter(when__gt=datetime.now())
        if obsolete_mtgs.count() > 0:
           log.error("Deleting %d obsolete meetings." % obsolete_mtgs.count())
           obsolete_mtgs.delete()

    if not options.disable_events:
        for committee in Committee.objects.filter(obsolete=False):
            log.info('Generating events for %s.' % committee)
            committee.create_events()
    			


if __name__ == '__main__':
    main()
