#!.env/bin/python
from lxml import etree
from datetime import datetime
import sys

from common.system import setup_django
setup_django(__file__)

from person.models import Person, PersonRole, Gender, RoleType, SenatorClass

class Progress(object):
    def __init__(self, step=None, total=None, stop=None):
        if not total and not step:
            raise Exception('Both step and total arguments are None')
        if total and not step:
            step = int(total / 20)
        self.step = step
        self.count = 0
        self.total = total
        self.stop = stop
    
    def tick(self):
        self.count += 1
        if not self.count % self.step:
            if self.total:
                percents = ' [%d%%]' % int((self.count / float(self.total)) * 100)
            else:
                percents = ''
            print 'Processed %d records%s' % (self.count, percents)
        if self.count == self.stop:
            print 'Reached stop value %d' % self.stop
            sys.exit()


class Processor(object):
    FIELD_MAPPING = {}

    def process(self, obj, node):
        for key in self.ATTRIBUTES:
            if key in self.REQUIRED_ATTRIBUTES:
                if not key in node.attrib:
                    raise Exception('Did not found required attribute %s in record %s' % (
                        key, self.display_node(node)))
            if key in node.attrib:
                field_name = self.FIELD_MAPPING.get(key, key)
                setattr(obj, field_name, self.convert(key, node.get(key)))
        return obj

    def display_node(self, node):
        return ', '.join('%s: %s' % x for x in node.attrib.iteritems())

    def convert(self, key, value):
        if hasattr(self, '%s_handler' % key):
            return getattr(self, '%s_handler' % key)(value)
        else:
            return value


class PersonProcessor(Processor):
    REQUIRED_ATTRIBUTES = ['id', 'firstname', 'lastname', 'bioguideid']
    ATTRIBUTES = [
        'id', 'firstname', 'lastname',
        'metavidid', 'pvsid', 'osid', 'youtubeid', 'gender',
        'birthday', 'middlename', 'religion', 'title', 'state',
        'district', 'namemod', 'nickname'
    ]
    GENDER_MAPPING = {'M': Gender.male, 'F': Gender.female}
    FIELD_MAPPING = {'id': 'pk'}

    def gender_handler(self, value):
        return self.GENDER_MAPPING[value]

    def birthday_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d')


class PersonRoleProcessor(Processor):
    REQUIRED_ATTRIBUTES = ['type', 'startdate', 'enddate']
    ATTRIBUTES = [
        'type', 'current', 'startdate', 'enddate', 'senator_class',
        'district', 'state', 'party',
    ]
    FIELD_MAPPING = {'type': 'role_type', 'class': 'senator_class'}
    ROLE_TYPE_MAPPING = {'rep': RoleType.congressman, 'sen': RoleType.senator,
                         'prez': RoleType.president}
    SENATOR_CLASS_MAPPING = {'1': SenatorClass.class1, '2': SenatorClass.class2,
                             '3': SenatorClass.class3}

    def type_handler(self, value):
        return self.ROLE_TYPE_MAPPING[value]

    def startdate_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d')

    def enddate_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d')

    def current_handler(self, value):
        return value == '1'

    def class_handler(self, value):
        return self.SENATOR_CLASS_MAPPING[value]


def main():
    person_processor = PersonProcessor()
    role_processor = PersonRoleProcessor()
    Person.objects.all().delete()
    tree = etree.parse('data/us/people.xml')
    total = len(tree.xpath('/people/person'))
    progress = Progress(total=total)
    print 'Processing persons'
    for person in tree.xpath('/people/person'):
        pobj = person_processor.process(Person(), person)
        pobj.save()

        for role in person.xpath('./role'):
            robj = role_processor.process(PersonRole(), role)
            robj.person = pobj
            robj.save()
        progress.tick()
    print 'Done'

def find():
    tree = etree.parse('data/us/people.xml')
    vars = set()
    varkey = 'namemod'
    for count, person in enumerate(tree.xpath('/people/person')):
        for key in person.attrib:
            if not key in (PERSON_ATTRIBUTES + ['name']):
                print key, person.get(key)
        if varkey:
            if varkey in person.attrib:
                vars.add(person.get(varkey))
    if varkey:
        print varkey, vars


if __name__ == '__main__':
    main()
