#!.env/bin/python
from lxml import etree
from datetime import datetime

from common.system import setup_django
setup_django(__file__)

from person.models import Person, PersonRole, Gender, RoleType, SenatorClass

class Processor(object):
    REQUIRED_ATTRIBUTES = ['id', 'firstname', 'lastname', 'bioguideid']
    ATTRIBUTES = [
        'id', 'firstname', 'lastname', 'bioguideid',
        'metavidid', 'pvsid', 'osid', 'youtubeid', 'gender',
        'birthday', 'middlename', 'religion', 'title', 'state',
        'district', 'namemod', 'nickname']
    GENDER_MAPPING = {'M': Gender.male, 'F': Gender.female}

    def process(self, obj, node):
        for key in self.ATTRIBUTES:
            if key in self.REQUIRED_ATTRIBUTES:
                if not key in node.attrib:
                    raise Exception('Did not found required attribute: %s' % key)
            if key in node.attrib:
                setattr(obj, key, self.convert(key, node.get(key)))
        return obj

    def convert(self, key, value):
        if hasattr(self, '%s_handler' % key):
            return getattr(self, '%s_handler' % key)(value)
        else:
            return value

    def gender_handler(self, value):
        return self.GENDER_MAPPING[value]

    def birthday_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d')


def main():
    proc = Processor()
    Person.objects.all().delete()
    tree = etree.parse('data/us/people.xml')
    for count, person in enumerate(tree.xpath('/people/person')):
        obj = proc.process(Person(), person)
        obj.save()
        if count > 10:
            break
    print 'OK'

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
