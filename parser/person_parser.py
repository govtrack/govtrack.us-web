"""
This script parse XML files and fill database
with Person and PersonRole objects.

Person model contains data about all people which were
a membe of Congress at least one time.

PersonRole contains data about role of current congress members.
"""
from lxml import etree
from datetime import datetime
import logging

from parser.progress import Progress
from parser.processor import Processor
from parser.models import File
from person.models import Person, PersonRole, Gender, RoleType, SenatorClass

log = logging.getLogger('parser.person_parser')

class PersonProcessor(Processor):
    """
    Person model contains data about all people which were
    a member of Congress at least one time.
    """

    REQUIRED_ATTRIBUTES = ['id', 'firstname', 'lastname']
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
        return datetime.strptime(value, '%Y-%m-%d').date()

    def enddate_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d').date()

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
        log.info('File %s was not changed' % XML_FILE)
        return

    person_processor = PersonProcessor()
    role_processor = PersonRoleProcessor()

    existing_persons = set(Person.objects.values_list('pk', flat=True))
    processed_persons = set()
    created_persons = set()

    tree = etree.parse(XML_FILE)
    total = len(tree.xpath('/people/person'))
    progress = Progress(total=total)
    log.info('Processing persons')

    for node in tree.xpath('/people/person'):
        # Wrap each iteration in try/except
        # so that if some node breaks the parsing process
        # then other nodes could be parsed
        try:
            person = person_processor.process(Person(), node)
            
            # Create cached name strings.
            person.set_names()

            # Now try to load the person with such ID from
            # database. If found it then just update it
            # else create new Person object
            try:
                ex_person = Person.objects.get(pk=person.pk)
                if person_processor.changed(ex_person, person) or options.force:
                    # If the person has PK of existing record
                    # then Django ORM will update existing record
                    if not options.force:
                        log.debug("Updated %s" % person)
                    person.save()
                    
            except Person.DoesNotExist:
                created_persons.add(person.pk)
                person.save()
                log.debug("Created %s" % person)

            processed_persons.add(person.pk)

            # Process roles of the person
            existing_roles = set(PersonRole.objects.filter(person=person).values_list('pk', flat=True))
            processed_roles = set()
            role_list = []
            for role in node.xpath('./role'):
                role = role_processor.process(PersonRole(), role)
                role.person = person
                role_list.append(role)
                # Overwrite an existing role if there is one that is different.
                try:
                    ex_role = PersonRole.objects.get(person=person, role_type=role.role_type, startdate=role.startdate, enddate=role.enddate)
                    processed_roles.add(ex_role.id)
                    role.id = ex_role.id
                    if role_processor.changed(ex_role, role) or options.force:
                        role.save()
                        if not options.force:
                            log.debug("Updated %s" % role)
                except PersonRole.DoesNotExist:
                    log.debug("Created %s" % role)
                    role.save()
                        
            # create the events for the roles after all have been loaded
            # because we don't create events for ends of terms and
            # starts of terms that are adjacent.
            if not options.disable_events:
                for i in xrange(len(role_list)):
                    role_list[i].create_events(
                        role_list[i-1] if i > 0 else None,
                        role_list[i+1] if i < len(role_list)-1 else None
                        )
            
        except Exception, ex:
            # Catch unexpected exceptions and log them
            log.error('', exc_info=ex)

        removed_roles = existing_roles - processed_roles
        for pk in removed_roles:
            pr = PersonRole.objects.get(pk=pk)
            log.debug("Deleted %s" % pr)
            pr.delete()
            
        progress.tick()

    # Remove person which were not found in XML file
    removed_persons = existing_persons - processed_persons
    for pk in removed_persons:
        p = Person.objects.get(pk=pk)
        log.debug("Deleted %s" % p)
        p.delete()

    log.info('Removed persons: %d' % len(removed_persons))
    log.info('Processed persons: %d' % len(processed_persons))
    log.info('Created persons: %d' % len(created_persons))

    File.objects.save_file(XML_FILE, content)


if __name__ == '__main__':
    main()
