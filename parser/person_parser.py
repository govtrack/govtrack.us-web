from lxml import etree
from datetime import datetime

from parser.progress import Progress
from parser.processor import Processor
from person.models import Person, PersonRole, Gender, RoleType, SenatorClass

class PersonProcessor(Processor):
    REQUIRED_ATTRIBUTES = ['id', 'firstname', 'lastname', 'biguideid']
    ATTRIBUTES = [
        'id', 'firstname', 'lastname', 'bioguideid',
        'metavidid', 'pvsid', 'osid', 'youtubeid', 'gender',
        'birthday', 'middlename',
        'namemod', 'nickname', 'twitterid',
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
        'district', 'state', 'party', 'url'
    ]
    FIELD_MAPPING = {'type': 'role_type', 'class': 'senator_class', 'url': 'website'}
    ROLE_TYPE_MAPPING = {'rep': RoleType.representative, 'sen': RoleType.senator,
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
    "Main parser logic"

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


def find():
    "Method for testing different things"

    print 'Hi world'
    #tree = etree.parse('data/us/people.xml')
    #vars = set()
    #varkey = 'namemod'
    #for count, person in enumerate(tree.xpath('/people/person')):
        #for key in person.attrib:
            #if not key in (PERSON_ATTRIBUTES + ['name']):
                #print key, person.get(key)
        #if varkey:
            #if varkey in person.attrib:
                #vars.add(person.get(varkey))
    #if varkey:
        #print varkey, vars


if __name__ == '__main__':
    main()
