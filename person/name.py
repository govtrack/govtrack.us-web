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
    elif person.id in (400204, 400295, 400659, 412293, 456814, 400061) \
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
        
    if hasattr(person, "role"):
        role = person.role # use this when it is set
    elif role_recent:
    	role = person.get_most_recent_role()
    else:
    	return name
        
    if role is None:
        return name
 
    if show_title:
        name = role.get_title_abbreviated() + ' ' + name
 
    if show_type:
        name += " (%s)" % role.get_title_abbreviated()
        
    if role and role.role_type in (RoleType.president, RoleType.vicepresident):
        show_district = False
 
    if show_party or show_district:
        name += ' ['
        if show_party:
            name += role.party[0] if role.party else '?'
        if show_party and show_district:
            name += '-'
        if show_district:
            name += role.state
            if role.role_type == RoleType.representative and role.district != 0:
                name += str(role.district)
                
        if role_recent and not role.current:
        	a, b = role.logical_dates(round_end=True)
        	name += ", %d-%d" % (a.year, b.year)
        	
        name += ']'
                 
    return name
