"""
Parser of data/us/committees.xml
"""

from lxml import etree
from datetime import datetime

from parser.progress import Progress
from parser.processor import Processor
from committee.models import Committee, Subcommittee, CommitteeType


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
    Parser of /committees/committee/subcommittee record.
    """

    REQUIRED_ATTRIBUTES = ['code', 'displayname']
    ATTRIBUTES = ['code', 'displayname']
    FIELD_MAPPING = {'displayname': 'name'}


def main():
    "Main parser logic"

    com_processor = CommitteeProcessor()
    subcom_processor = SubcommitteeProcessor()
    Committee.objects.all().delete()
    tree = etree.parse('data/us/committees.xml')
    total = len(tree.xpath('/committees/committee'))
    progress = Progress(total=total)
    print 'Processing committees'
    for committee in tree.xpath('/committees/committee'):
        cobj = com_processor.process(Committee(), committee)
        cobj.save()

        for subcom in committee.xpath('./subcommittee'):
            sobj = subcom_processor.process(Subcommittee(), subcom)
            sobj.committee = cobj
            sobj.save()
        progress.tick()


def find():
    "Method for testing different things"

    tree = etree.parse('data/us/committees.xml')
    vars = set()
    varkey = None
    attrs = set()
    for count, item in enumerate(tree.xpath('/committees/committee')):
        attrs.update(item.attrib.keys())
        if varkey:
            if varkey in item.attrib:
                vars.add(item.get(varkey))
    if varkey:
        print varkey, vars
    print 'Attributes: %s' % ', '.join(attrs)


if __name__ == '__main__':
    main()
