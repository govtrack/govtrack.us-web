"""
Parse list of committees which ever were in Congress.
Parse members of current congress committees.
"""
from lxml import etree
from datetime import datetime
import logging

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from committee.models import (Committee, CommitteeType, CommitteeMember,
                              CommitteeMemberRole, CommitteeMeeting)
from person.models import Person

log = logging.getLogger('parser.committee_parser')

class CommitteeProcessor(Processor):
    """
    Parser of /committees/committe record.
    """

    REQUIRED_ATTRIBUTES = ['type', 'code', 'displayname']
    ATTRIBUTES = ['type', 'code', 'displayname', 'abbrev', 'url', 'obsolete']
    FIELD_MAPPING = {'type': 'committee_type', 'displayname': 'name'}
    TYPE_MAPPING = {'senate': CommitteeType.senate,
                    'joint': CommitteeType.joint,
                    'house': CommitteeType.house}

    def type_handler(self, value):
        return self.TYPE_MAPPING[value]


class SubcommitteeProcessor(Processor):
    """
    Parser of /committees/committee/subcommittee records.
    """

    REQUIRED_ATTRIBUTES = ['code', 'displayname']
    ATTRIBUTES = ['code', 'displayname']
    FIELD_MAPPING = {'displayname': 'name'}


class CommitteeMemberProcessor(Processor):
    """
    Parser of /committee/member.
    """

    REQUIRED_ATTRIBUTES = ['id']
    ATTRIBUTES = ['id', 'role']
    FIELD_MAPPING = {'id': 'person'}
    ROLE_MAPPING = {
        'Ex Officio': CommitteeMemberRole.exofficio,
        'Chairman': CommitteeMemberRole.chairman,
        'Chair': CommitteeMemberRole.chairman,
        'Ranking Member': CommitteeMemberRole.ranking_member,
        'Vice Chairman': CommitteeMemberRole.vice_chairman,
        'Member': CommitteeMemberRole.member,
    }
    DEFAULT_VALUES = {'role': 'Member'}

    def id_handler(self, value):
        return Person.objects.get(pk=value)

    def role_handler(self, value):
        return self.ROLE_MAPPING[value]

class CommitteeMeetingProcessor(Processor):
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

    com_processor = CommitteeProcessor()
    subcom_processor = SubcommitteeProcessor()
    member_processor = CommitteeMemberProcessor()
    meeting_processor = CommitteeMeetingProcessor()

    log.info('Processing committees')
    COMMITTEES_FILE = 'data/us/committees.xml'
    # If file changed then delete committees and set
    # this varible to True, it will be the signal
    # to run committee members parser anyway
    committees_deleted = False

    if not File.objects.is_changed(COMMITTEES_FILE) and not options.force:
        log.info('File %s was not changed' % COMMITTEES_FILE)
    else:
        # Delete all existing committees and
        # records which are linked to them via ForeignKey
        Committee.objects.all().delete()
        committees_deleted = True

        tree = etree.parse(COMMITTEES_FILE)
        total = len(tree.xpath('/committees/committee'))
        progress = Progress(total=total)
        for committee in tree.xpath('/committees/committee'):
            cobj = com_processor.process(Committee(), committee)
            cobj.save()

            for subcom in committee.xpath('./subcommittee'):
                sobj = subcom_processor.process(Committee(), subcom)
                sobj.code = cobj.code + sobj.code
                sobj.committee = cobj
                sobj.save()
            progress.tick()

        File.objects.save_file(COMMITTEES_FILE)

    log.info('Processing committee members')
    MEMBERS_FILE = 'data/us/112/committees.xml'
    file_changed = File.objects.is_changed(MEMBERS_FILE)

    if not committees_deleted and not file_changed and not options.force:
        log.info('File %s was not changed' % MEMBERS_FILE)
    else:
        tree = etree.parse(MEMBERS_FILE)
        total = len(tree.xpath('/committees/committee/member'))
        progress = Progress(total=total, name='committees')
        
        CommitteeMember.objects.all().delete()

        # Process committee nodes
        for committee in tree.xpath('/committees/committee'):
            cobj = Committee.objects.get(code=committee.get('code'))

            # Process members of current committee node
            for member in committee.xpath('./member'):
                mobj = member_processor.process(CommitteeMember(), member)
                mobj.committee = cobj
                mobj.save()
            
            # Process all subcommittees of current committee node
            for subcom in committee.xpath('./subcommittee'):
                try:
                    sobj = Committee.objects.get(code=committee.get('code')+subcom.get('code'), committee=cobj)
                except Committee.DoesNotExist:
                    log.error('In committee membership file, reference to unknown committee %s-%s' % (
                        cobj.code, subcom.get('code')))
                else:
                    # Process members of current subcommittee node
                    for member in subcom.xpath('./member'):
                        mobj = member_processor.process(CommitteeMember(), member)
                        mobj.committee = sobj
                        mobj.save()

            progress.tick()

        File.objects.save_file(MEMBERS_FILE)

    log.info('Processing committee schedule')
    SCHEDULE_FILE = 'data/us/112/committeeschedule.xml'
    file_changed = File.objects.is_changed(SCHEDULE_FILE)

    if not committees_deleted and not file_changed and not options.force:
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
            except Committee.DoesNotExist:
                log.error('Could not load Committee object for meeting %s' % meeting_processor.display_node(meeting))

        for committee in Committee.objects.all():
            if not options.disable_events:
                committee.create_events()
            
        File.objects.save_file(SCHEDULE_FILE)
    

if __name__ == '__main__':
    main()
