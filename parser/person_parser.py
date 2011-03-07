"""
This script parse XML files and fill database
with Person and PersonRole objects.

Person model contains data about all people which were
a membe of Congress at least one time.

PersonRole contains data about role of current congress members.
"""
from lxml import etree
from datetime import datetime

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from person.models import Person, PersonRole, Gender, RoleType, SenatorClass

class PersonProcessor(Processor):
    """
    Person model contains data about all people which were
    a member of Congress at least one time.
    """

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

    def id_handler(self, value):
        return int(value)


class PersonRoleProcessor(Processor):
    """
    PersonRole contains data about role of current congress members.
    """

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
    """
    Update Person and PersonRole models.
    
    Do safe update: touch only those records
    which have been changed.
    """

    XML_FILE = 'data/us/people.xml'
    content = open(XML_FILE).read()

    if not File.objects.is_changed(XML_FILE, content=content):
        print 'File %s was not changed' % XML_FILE
        return

    person_processor = PersonProcessor()
    role_processor = PersonRoleProcessor()

    existing_persons = set(Person.objects.values_list('pk', flat=True))
    processed_persons = set()
    created_persons = set()

    tree = etree.parse(XML_FILE)
    total = len(tree.xpath('/people/person'))
    progress = Progress(total=total)
    print 'Processing persons'

    for node in tree.xpath('/people/person'):
        person = person_processor.process(Person(), node)

        # Now try to load the person with such ID from
        # database. If found it then just update it
        # else create new Person object
        try:
            ex_person = Person.objects.get(pk=person.pk)
        except Person.DoesNotExist:
            created_persons.add(person.pk)

        # If the person has PK of existing record
        # then Django ORM will update existing record
        person.save()

        processed_persons.add(person.pk)

        # Process roles of the person
        # For simplicity just remove roles
        # of existing record
        person.roles.all().delete()
        for role in node.xpath('./role'):
            role = role_processor.process(PersonRole(), role)
            role.person = person
            role.save()

        progress.tick()

    # Remove person which were not found in XML file
    removed_persons = existing_persons - processed_persons
    import pdb; pdb.set_trace()
    for pk in removed_persons:
        Person.objects.get(pk=pk).delete()

    print 'Removed persons: %d' % len(removed_persons)
    print 'Processed persons: %d' % len(processed_persons)
    print 'Created persons: %d' % len(created_persons)

    File.objects.save_file(XML_FILE, content)


if __name__ == '__main__':
    main()
