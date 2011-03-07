"""
Parse list of committees which ever were in Congress.
Parse members of current congress committees.
"""

from lxml import etree
from datetime import datetime

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from committee.models import (Committee, CommitteeType, CommitteeMember,
                              CommitteeMemberRole)
from person.models import Person


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
        'Ranking Member': CommitteeMemberRole.ranking_member,
        'Vice Chairman': CommitteeMemberRole.vice_chairman,
        'Member': CommitteeMemberRole.member,
    }
    DEFAULT_VALUES = {'role': 'Member'}

    def id_handler(self, value):
        return Person.objects.get(pk=value)

    def role_handler(self, value):
        return self.ROLE_MAPPING[value]


def main():
    """
    Process committees, subcommittees and
    members of current congress committees.
    """

    com_processor = CommitteeProcessor()
    subcom_processor = SubcommitteeProcessor()
    member_processor = CommitteeMemberProcessor()

    print 'Processing committees'
    COMMITTEES_FILE = 'data/us/committees.xml'
    # If file changed then delete committees and set
    # this varible to True, it will be the signal
    # to run committee members parser anyway
    committees_deleted = False

    if not File.objects.is_changed(COMMITTEES_FILE):
        print 'File %s was not changed' % COMMITTEES_FILE
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
                sobj.committee = cobj
                sobj.save()
            progress.tick()

        File.objects.save_file(COMMITTEES_FILE)

    print 'Processing committee members'
    MEMBERS_FILE = 'data/us/112/committees.xml'
    file_changed = File.objects.is_changed(MEMBERS_FILE)

    if not committees_deleted and not file_changed:
        print 'File %s was not changed' % MEMBERS_FILE
    else:
        tree = etree.parse(MEMBERS_FILE)
        total = len(tree.xpath('/committees/committee/member'))
        progress = Progress(total=total, name='committees')

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
                    sobj = Committee.objects.get(code=subcom.get('code'), committee=cobj)
                except Committee.DoesNotExist:
                    print 'Could not process SubCom with code %s which parent Com has code %s' % (
                        subcom.get('code'), cobj.code)
                else:
                    # Process members of current subcommittee node
                    for member in subcom.xpath('./member'):
                        mobj = member_processor.process(CommitteeMember(), member)
                        mobj.committee = sobj
                        mobj.save()

            progress.tick()

        File.objects.save_file(MEMBERS_FILE)


if __name__ == '__main__':
    main()
