from datetime import datetime

from person.models import RoleType

def get_dopplegangers():
    # Return a list of person IDs for people that have the same
    # first and last name for whom we should display a suffix
    # (if they also have the same or no middle name, and if set) or
    # a middle name (if set).
    # (Note: Junior-senior pairs often have the same middle name!)
    if hasattr(get_dopplegangers, 'data'): return get_dopplegangers.data
    from person.models import Person
    from collections import defaultdict

    get_dopplegangers.data = { }

    # Use suffixes for people with the same first, middle, and last name.
    # We assume that suffixes in those cases are unique.
    data = defaultdict(lambda : [])
    for id_name_role in Person.objects.values_list("id", "firstname", "middlename", "lastname", "roles__role_type")\
                         .exclude(namemod=None).distinct():
        data[id_name_role[1:]].append(id_name_role[0])
    get_dopplegangers.data["suffix"] = set(sum([v for k, v in data.items() if len(v) > 1], []))

    # Use middle names for people with the same first and last name, except
    # those above that are distinguished by suffixes already.
    data = defaultdict(lambda : [])
    for id_name_role in Person.objects.values_list("id", "firstname", "lastname", "roles__role_type")\
                         .exclude(middlename=None).distinct():
        data[id_name_role[1:]].append(id_name_role[0])
    get_dopplegangers.data["middle"] = set(sum([v for k, v in data.items() if len(v) > 1], [])) - get_dopplegangers.data["suffix"]

    # Also use suffixes for people with the same first and last name
    # and different middle names when there is no middle name.
    data = defaultdict(lambda : [])
    for id_name_role in Person.objects.values_list("id", "firstname", "lastname", "roles__role_type")\
                         .exclude(namemod=None).distinct():
        data[id_name_role[1:]].append(id_name_role[0])
    get_dopplegangers.data["suffix"] |= set(sum([v for k, v in data.items() if len(v) > 1], [])) - get_dopplegangers.data["middle"]

    return get_dopplegangers.data

def get_person_name(person,
				firstname_position=None, firstname_style=None,
				role_recent=None,
                show_title=True, show_party=True, show_district=True, show_type=False):

    firstname = person.firstname

    if firstname.endswith('.'):
        firstname = person.middlename

    # Some people have middle names that are crucial for distinguishing
    # who the person is (i.e. 400702 John Quincy Adams who is not John Adams).
    elif person.middlename and person.id in get_dopplegangers()["middle"]:
        firstname += " " + person.middlename

    # Others use their middle names with such regularity that it is hard
    # to recognize the legislator without it, but we'll only display it
    # in first-last format. This is often maiden names.
    elif person.id in (400204, 400295, 400659, 412293, 456814, 400061, 412750) \
      and firstname_position == 'before':
        firstname += " " + person.middlename

    if person.nickname:
        if firstname_style == None:
            firstname += " \u201c%s\u201d" % person.nickname
        elif firstname_style == "nickname" and len(person.nickname) < len(firstname):
            firstname = person.nickname
 
    if firstname_position == 'before':
        name = firstname + ' ' + person.lastname
        if person.namemod and person.id in get_dopplegangers()["suffix"]:
            name += ' ' + person.namemod
    
    elif firstname_position == 'after':
        name = person.lastname + ', ' + firstname
    else:
        name = person.lastname

    # Add their title, party, state, and district, to the extent appropriate for their role.

    # Which role to use for this part?
    if getattr(person, "role", None):
        # Use this attribute when it is set.
        roles = { person.role }
    elif hasattr(person, "_roles"):
        # Use this attribute when it is set.
        roles = person._roles
    elif role_recent:
        role = person.get_most_recent_role()
        roles = { role } if role else set()
    else:
    	roles = set()

    if len(roles) == 0:
        return name

    roles = sorted(roles, key = lambda r : r.startdate)

    def combine(formatter, separator="/"):
        items = []
        for role in roles:
            item = formatter(role)
            if items and item == items[-1]: continue
            items.append(item)
        return separator.join(items)

    if show_title:
        name = combine(lambda role : role.get_title_abbreviated()) + ' ' + name

    if show_type:
        name += " (" + combine(lambda role : role.get_title_abbreviated()) + ")"

    has_state_or_district = False
    for role in roles:
        if role.role_type not in (RoleType.president, RoleType.vicepresident):
            has_state_or_district = True
 
    if show_party or (show_district and has_state_or_district):
        name += ' ['

        if show_party:
            # If the party is the same in all of the roles, show it.
            if len(set(role.party for role in roles)) == 1:
                name += combine(lambda role : role.party[0] if role.party else '?')
                if show_district and has_state_or_district:
                    name += '-'
                show_party = False # don't show below

        if show_district and has_state_or_district:
            # If the state is the same in all of the roles, show it.
            # Unless we didn't show the party yet, since the party should
            # preceed the state.
            show_state = True
            if not show_party:
                state = list(set(role.state for role in roles if role.state))
                if len(state) == 1:
                    name += state[0]
                    show_state = False # don't show below

            # Combine the district, plus the party and state if they were not the
            # same in all of the roles.
            def district_combiner(role):
                item = ""
                if show_party: item += (role.party[0] if role.party else '?')
                if show_state and role.state:
                    if show_party: item += "-"
                    item += role.state
                if role.role_type == RoleType.representative and role.district != 0:
                    item += str(role.district)
                return item
            name += combine(district_combiner)
                
        if role_recent and not roles[0].current:
        	a, b = roles[0].logical_dates(round_end=True)
        	name += ", %d-%d" % (a.year, b.year)
        	
        name += ']'
                 
    return name
