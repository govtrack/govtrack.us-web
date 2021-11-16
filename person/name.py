from datetime import datetime

from person.models import RoleType

def get_person_name(person,
				firstname_position=None, show_suffix=False, firstname_style=None,
				role_recent=None,
                show_title=True, show_party=True, show_district=True, show_type=False):

    firstname = person.firstname

    if firstname.endswith('.'):
        firstname = person.middlename
    elif person.id in (400702,): # John Quincy Adams
        firstname += " " + person.middlename

    if person.nickname:
        if firstname_style == None:
            firstname += " \u201c%s\u201d" % person.nickname
        elif firstname_style == "nickname" and len(person.nickname) < len(firstname):
            firstname = person.nickname
 
    if firstname_position == 'before':
        name = firstname + ' ' + person.lastname
    elif firstname_position == 'after':
        name = person.lastname + ', ' + firstname
    else:
        name = person.lastname
        
    if show_suffix:
        if person.namemod:
            name += ' ' + person.namemod
    
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
