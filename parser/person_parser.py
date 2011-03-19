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


def main(options):
    """
    Update Person and PersonRole models.
    
    Do safe update: touch only those records
    which have been changed.
    """

    XML_FILE = 'data/us/people.xml'
    content = open(XML_FILE).read()

    if not File.objects.is_changed(XML_FILE, content=content) and not options.force:
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
            if person_processor.changed(ex_person, person) or options.force:
                # If the person has PK of existing record
                # then Django ORM will update existing record
                if not options.force: print "Updated", person
                person.save()
                
        except Person.DoesNotExist:
            created_persons.add(person.pk)
            person.save()
            print "Created", person

        processed_persons.add(person.pk)

        # Process roles of the person
        existing_roles = set(PersonRole.objects.filter(person=person).values_list('pk', flat=True))
        processed_roles = set()
        for role in node.xpath('./role'):
            role = role_processor.process(PersonRole(), role)
            role.person = person
            # Overwrite an existing role if there is one that is different.
            try:
                ex_role = PersonRole.objects.get(person=person, role_type=role.role_type, startdate=role.startdate, enddate=role.enddate)
                processed_roles.add(ex_role.id)
                role.id = ex_role.id
                if role_processor.changed(ex_role, role) or options.force:
                    role.save()
                    role.create_events()
                    if not options.force: print "Updated", role
            except PersonRole.DoesNotExist:
                print "Created", role
                role.save()
                role.create_events()

        removed_roles = existing_roles - processed_roles
        for pk in removed_roles:
            pr = PersonRole.objects.get(pk=pk)
            print "Deleted", pr
            pr.delete()
            
        progress.tick()

    # Remove person which were not found in XML file
    removed_persons = existing_persons - processed_persons
    for pk in removed_persons:
        p = Person.objects.get(pk=pk)
        print "Deleted", p
        p.delete()

    print 'Removed persons: %d' % len(removed_persons)
    print 'Processed persons: %d' % len(processed_persons)
    print 'Created persons: %d' % len(created_persons)

    File.objects.save_file(XML_FILE, content)


if __name__ == '__main__':
    main()
