"""
Parser of data/us/committees.xml
"""

from lxml import etree
from datetime import datetime

from parser.progress import Progress
from parser.processor import Processor
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
    "Main parser logic"

    com_processor = CommitteeProcessor()
    subcom_processor = SubcommitteeProcessor()
    member_processor = CommitteeMemberProcessor()
    Committee.objects.all().delete()

    print 'Processing committees'
    tree = etree.parse('data/us/committees.xml')
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

    print 'Processing committee members'
    tree = etree.parse('data/us/112/committees.xml')
    total = len(tree.xpath('/committees/committee/member'))
    progress = Progress(total=total)
    for committee in tree.xpath('/committees/committee'):
        cobj = Committee.objects.get(code=committee.get('code'))

        for member in committee.xpath('./member'):
            mobj = member_processor.process(CommitteeMember(), member)
            mobj.committee = cobj
            mobj.save()

        for subcom in committee.xpath('./subcommittee'):
            try:
                sobj = Committee.objects.get(code=subcom.get('code'), committee=cobj)
            except Committee.DoesNotExist:
                print 'Could not process SubCom with code %s which parent Com has code %s' % (
                    subcom.get('code'), cobj.code)
            else:
                for member in subcom.xpath('./member'):
                    mobj = member_processor.process(CommitteeMember(), member)
                    mobj.committee = sobj
                    mobj.save()

        progress.tick()


def check():
    print 'Checking integrity'
    for com in Committee.objects.filter(committee=None):#, code='SSFR'):
        members = set([x.person_id for x in com.members.all()])
        members2 = set()
        for subcom in com.subcommittees.all():
            members2.update(set([x.person_id for x in subcom.members.all()]))
        print com
        if len(members) >= len(members2):
            print 'OK'
        else:
            print 'FALSE'
            print 'Members: %d' % len(members)
            print 'Members of subdivisions: %d' % len(members2)
            print 'Equal: %s' % (members == members2)


def find():
    "Method for testing different things"

    tree = etree.parse('data/us/112/committees.xml')
    vars = set()
    varkey = 'role'
    attrs = set()
    for count, item in enumerate(tree.xpath('/committees/committee/member')):
        attrs.update(item.attrib.keys())
        if varkey:
            if varkey in item.attrib:
                vars.add(item.get(varkey))
    if varkey:
        print varkey, vars
    print 'Attributes: %s' % ', '.join(attrs)


if __name__ == '__main__':
    main()
