"""
This script parse XML files and fill database
with Person and PersonRole objects.

Person model contains data about all people which were
a membe of Congress at least one time.

PersonRole contains data about role of current congress members.
"""
from datetime import datetime
import logging, pprint

from parser.progress import Progress
from parser.processor import YamlProcessor, yaml_load
from parser.models import File
from person.models import Person, PersonRole, Gender, RoleType, SenatorClass, SenatorRank
from us import get_congress_dates

from django.db import transaction
from settings import CURRENT_CONGRESS, CONGRESS_LEGISLATORS_PATH

log = logging.getLogger('parser.person_parser')

class PersonProcessor(YamlProcessor):
    """
    Person model contains data about all people which were
    a member of Congress at least one time.
    """

    REQUIRED_ATTRIBUTES = ['id__govtrack', 'name__first', 'name__last']
    ATTRIBUTES = [
        'id__govtrack', 'name__first', 'name__last',
        'name__middle', 'name__suffix', 'name__nickname',
        'id__bioguide', 'id__votesmart', 'id__opensecrets', 'id__cspan',
        'social__youtube', 'social__twitter',
        'bio__birthday', 'bio__gender',
    ]
    GENDER_MAPPING = {'M': Gender.male, 'F': Gender.female}
    FIELD_MAPPING = {
        'id__govtrack': 'id',
        'id__bioguide': 'bioguideid',
        'id__votesmart': 'pvsid',
        'id__opensecrets': 'osid',
        'id__cspan': 'cspanid',
        'social__youtube': 'youtubeid',
        'social__twitter': 'twitterid',
        'name__first': 'firstname',
        'name__last': 'lastname',
        'bio__birthday': 'birthday',
        'bio__gender': 'gender',
        'name__middle': 'middlename',
        'name__suffix': 'namemod',
        'name__nickname': 'nickname',
    }

    def bio__gender_handler(self, value):
        return self.GENDER_MAPPING[value]

    def bio__birthday_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d')

    def id__govtrack_handler(self, value):
        return int(value)
    def id__cspan_handler(self, value):
        return int(value)


class PersonRoleProcessor(YamlProcessor):
    """
    PersonRole contains data about role of current congress members.
    """

    REQUIRED_ATTRIBUTES = ['type', 'start', 'end']
    ATTRIBUTES = [
        'type', 'start', 'end', 'class', 'state_rank',
        'district', 'state', 'party', 'caucus', 'url', 'phone',
    ]
    FIELD_MAPPING = {
        'type': 'role_type',
        'start': 'startdate',
        'end': 'enddate',
        'class': 'senator_class',
        'state_rank': 'senator_rank',
        'url': 'website'
    }
    ROLE_TYPE_MAPPING = {
        'rep': RoleType.representative,
        'sen': RoleType.senator,
        'prez': RoleType.president,
        'viceprez': RoleType.vicepresident}
    SENATOR_CLASS_MAPPING = {1: SenatorClass.class1, 2: SenatorClass.class2,
                             3: SenatorClass.class3}
    SENATOR_RANK_MAPPING = {'senior': SenatorRank.senior, 'junior': SenatorRank.junior}

    def type_handler(self, value):
        return self.ROLE_TYPE_MAPPING[value]

    def start_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d').date()

    def end_handler(self, value):
        return datetime.strptime(value, '%Y-%m-%d').date()

    def class_handler(self, value):
        return self.SENATOR_CLASS_MAPPING[value]

    def state_rank_handler(self, value):
        return self.SENATOR_RANK_MAPPING[value]

@transaction.atomic
def main(options):
    """
    Update Person and PersonRole models.
    
    Do safe update: touch only those records
    which have been changed.
    """

    BASE_PATH = CONGRESS_LEGISLATORS_PATH
    SRC_FILES = ['legislators-current', 'legislators-historical', 'legislators-social-media', 'executive'] # order matters

    for p in SRC_FILES:
        f = BASE_PATH + p + ".yaml"
        if not File.objects.is_changed(f) and not options.force:
            log.info('File %s was not changed' % f)
        else:
            # file modified...
            break
    else:
        # no 'break' ==> no files modified
        return

    # Start parsing.
    
    had_error = False

    # Get combined data.
    legislator_data = { }
    leg_id_map = { }
    for p in SRC_FILES:
        log.info('Opening %s...' % p)
        f = BASE_PATH + p + ".yaml"
        y = yaml_load(f)
        for m in y:
            if p == "legislators-current":
                # We know all terms but the last are non-current and the last is.
                for r in m["terms"]: r["current"] = False
                m["terms"][-1]["current"] = True
            elif p == "legislators-historical":
                # We know all terms are non-current.
                for r in m["terms"]: r["current"] = False

            if p != 'legislators-social-media':
                govtrack_id = m["id"].get("govtrack")
                
                # For the benefit of the social media file, make a mapping of IDs.
                for k, v in m["id"].items():
                    if type(v) != list:
                        leg_id_map[(k,v)] = govtrack_id
            else:
                # GovTrack IDs are not always listed in this file.
                govtrack_id = None
                for k, v in m["id"].items():
                    if type(v) != list and (k, v) in leg_id_map:
                        govtrack_id = leg_id_map[(k,v)]
                        break
            
            if not govtrack_id:
                print("No GovTrack ID:")
                pprint.pprint(m)
                had_error = True
                continue
                
            if govtrack_id not in legislator_data:
                legislator_data[govtrack_id] = m
            elif p == "legislators-social-media":
                legislator_data[govtrack_id]["social"] = m["social"]
            elif p == "executive":
                legislator_data[govtrack_id]["terms"].extend( m["terms"] )
            else:
                raise ValueError("Duplication in an unexpected way (%d, %s)." % (govtrack_id, p))
    
    person_processor = PersonProcessor()
    role_processor = PersonRoleProcessor()

    existing_persons = set(Person.objects.values_list('pk', flat=True))
    processed_persons = set()
    created_persons = set()

    progress = Progress(total=len(legislator_data))
    log.info('Processing persons')

    for node in legislator_data.values():
        # Wrap each iteration in try/except
        # so that if some node breaks the parsing process
        # then other nodes could be parsed
        try:
            person = person_processor.process(Person(), node)
            
            # Create cached name strings. This is done again later
            # after the roles are updated.
            person.set_names()

            # Now try to load the person with such ID from
            # database. If found it then just update it
            # else create new Person object
            try:
                ex_person = Person.objects.get(pk=person.pk)
                if person_processor.changed(ex_person, person) or options.force:
                    # If the person has PK of existing record,
                    # coming in via the YAML-specified GovTrack ID,
                    # then Django ORM will update existing record
                    if not options.force:
                        log.warn("Updated %s" % person)
                    person.save()
                    
            except Person.DoesNotExist:
                created_persons.add(person.pk)
                person.save()
                log.warn("Created %s" % person)

            processed_persons.add(person.pk)

            # Parse all of the roles.
            new_roles = []
            for termnode in node['terms']:
                role = role_processor.process(PersonRole(), termnode)
                role.person = person
                role.extra = filter_yaml_term_structure(termnode) # copy in the whole YAML structure

                # Is this role current? For legislators, same as whether it came from legislators-current, which eases Jan 3 transitions when we can't distinguish by date.
                if "current" in termnode:
                    role.current = termnode["current"]

                # But executives...
                else:
                    now = datetime.now().date()
                    role.current = role.startdate <= now and role.enddate >= now
                    # Because of date overlaps at noon transition dates, ensure that only the last term that covers
                    # today is current --- reset past roles to not current. Doesn't handle turning off retirning people tho.
                    for r in new_roles: r.current = False

                # Scan for most recent leadership role within the time period of this term,
                # which isn't great for Senators because it's likely it changed a few times
                # within a term, especially if there was a party switch.
                role.leadership_title = None
                for leadership_node in node.get("leadership_roles", []):
                    # must match on date and chamber
                    if leadership_node["start"] >= role.enddate.isoformat(): continue # might start on the same day but is for the next Congress
                    if "end" in leadership_node and leadership_node["end"] <= role.startdate.isoformat(): continue # might start on the same day but is for the previous Congress
                    if leadership_node["chamber"] != RoleType.by_value(role.role_type).congress_chamber.lower(): continue
                    role.leadership_title = leadership_node["title"]

                new_roles.append(role)

            # Try matching the new roles to existing db records. Since we don't have a primry key
            # in the source data, we have to match on the record values. But because of errors in data,
            # term start/end dates can change, so matching has to be a little fuzzy.
            existing_roles = list(PersonRole.objects.filter(person=person))
            matches = []
            def run_match_rule(rule):
                import itertools
                for new_role, existing_role in itertools.product(new_roles, existing_roles):
                    if new_role not in new_roles or existing_role not in existing_roles: continue # already matched on a previous iteration
                    if new_role.role_type != existing_role.role_type: continue
                    if new_role.state != existing_role.state: continue
                    if rule(new_role, existing_role):
                        matches.append((new_role, existing_role))
                        new_roles.remove(new_role)
                        existing_roles.remove(existing_role)

            # First match exactly, then exact on just one date, then on contractions and expansions.
            run_match_rule(lambda new_role, existing_role : new_role.startdate == existing_role.startdate and new_role.enddate == existing_role.enddate)
            run_match_rule(lambda new_role, existing_role : new_role.startdate == existing_role.startdate or new_role.enddate == existing_role.enddate)
            run_match_rule(lambda new_role, existing_role : new_role.startdate >= existing_role.startdate and new_role.enddate <= existing_role.enddate)
            run_match_rule(lambda new_role, existing_role : new_role.startdate <= existing_role.startdate and new_role.enddate >= existing_role.enddate)

            # Update the database entries that correspond with records in the data file.
            did_update_any = False
            for new_role, existing_role in matches:
                new_role.id = existing_role.id
                if role_processor.changed(existing_role, new_role) or options.force:
                    new_role.save()
                    did_update_any = True
                    if not options.force:
                        log.warn("Updated %s" % new_role)

            # If we have mutliple records on disk that didn't match and multiple records in the database
            # that didn't match, then we don't know how to align them.
            if len(new_roles) > 0 and len(existing_roles) > 0:
                print(new_roles)
                print(existing_roles)
                raise Exception("There is an unmatched role.")

            # Otherwise if there are any unmatched new roles, we can just add them.
            for role in new_roles:
                log.warn("Created %s" % role)
                role.save()
                did_update_any = True
            
            # And likewise for any existing roles that are left over.
            for pr in existing_roles:
                print(pr.person.id, pr)
                raise ValueError("Deleted role??")
                log.warn("Deleted %s" % pr)
                pr.delete()
            
            if did_update_any and not options.disable_events:
                # Create the events for the roles after all have been loaded
                # because we don't create events for ends of terms and
                # starts of terms that are adjacent. Refresh the list to get
                # the roles in order.
                role_list = list(PersonRole.objects.filter(person=person).order_by('startdate'))
                for i in range(len(role_list)):
                    role_list[i].create_events(
                        role_list[i-1] if i > 0 else None,
                        role_list[i+1] if i < len(role_list)-1 else None
                        )
            
            # The name can't be determined until all of the roles are set. If
            # it changes, re-save. Unfortunately roles are cached so this actually
            # doesn't work yet. Re-run the parser to fix names.
            nn = (person.name, person.sortname)
            if hasattr(person, "role"): delattr(person, "role") # clear the cached info
            person._most_recent_role = None # clear cache here too
            person.set_names()
            if nn != (person.name, person.sortname):
                log.warn("%s is now %s." % (nn[0], person.name))
                person.save()
            
        except Exception as ex:
            # Catch unexpected exceptions and log them
            pprint.pprint(node)
            log.error('', exc_info=ex)
            had_error = True

        progress.tick()

    log.info('Processed persons: %d' % len(processed_persons))
    log.info('Created persons: %d' % len(created_persons))
    
    if not had_error:
        # Remove person which were not found in XML file
        removed_persons = existing_persons - processed_persons
        for pk in removed_persons:
            p = Person.objects.get(pk=pk)
            if p.roles.all().count() > 0:
                log.warn("Missing? Deleted? %d: %s" % (p.id, p))
            else:
                log.warn("Deleting... %d: %s (remember to prune_index!)" % (p.id, p))
                raise Exception("Won't delete!")
                p.delete()
        log.info('Missing/deleted persons: %d' % len(removed_persons))
    
        # Mark the files as processed.
        for p in SRC_FILES:
            f = BASE_PATH + p + ".yaml"
            File.objects.save_file(f)

    update_twitter_list()

def filter_yaml_term_structure(node):
    ret = { }
    for k, v in node.items():
        if k in PersonRoleProcessor.ATTRIBUTES: continue # no need to store things we've saved in schema'd fields
        if k == "current": continue # we add this
        ret[k] = v
    if len(ret) == 0: return None # simplify storage
    return ret

def update_twitter_list():
    from django.conf import settings

    if not settings.TWITTER_OAUTH_TOKEN: return

    def chunk(seq, count):
        ret = []
        for x in seq:
            ret.append(x)
            if len(ret) == count:
                yield ret
                ret = []
        if len(ret) > 0:
            yield ret

    # Get all of the Twitter handles of currently serving MoCs.
    from person.models import Person
    handles = set(Person.objects.filter(roles__current=True).exclude(twitterid=None).values_list("twitterid", flat=True))
    handles = { h.lower() for h in handles }

    # Get the handles currently in the list.
    import twitter
    twitter = twitter.Api(consumer_key=settings.TWITTER_OAUTH_TOKEN, consumer_secret=settings.TWITTER_OAUTH_TOKEN_SECRET,
                          access_token_key=settings.TWITTER_ACCESS_TOKEN, access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET)
    existing = twitter.GetListMembers(owner_screen_name="govtrack", slug="members-of-congress", skip_status=True)
    existing = { u.screen_name.lower() for u in existing }

    # Add anyone not yet listed.
    if handles-existing: print("Adding to our Twitter list:", handles-existing)
    for hh in chunk(handles - existing, 100):
        twitter.CreateListsMember(
          screen_name=hh,
          owner_screen_name="govtrack", slug="members-of-congress")

    # Remove anyone that shouldn't be listed.
    if existing-handles: print("Removing from our Twitter list:", existing-handles)
    for hh in chunk(existing - handles, 100):
        twitter.DestroyListsMember(
          screen_name=hh,
          owner_screen_name="govtrack", slug="members-of-congress")
 		

if __name__ == '__main__':
    main()
