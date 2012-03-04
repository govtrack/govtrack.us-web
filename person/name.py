from datetime import datetime

from person.models import RoleType

def get_person_name(person,
				firstname_position=None, show_suffix=False,
				role_date=None, role_congress=None, role_recent=None, role_year=None,
                show_title=True, show_party=True, show_district=True, show_type=False):
    """
    Args:
        role_date - the date from which the person role should be extracted
        role_congress - the congress number from which the person role should be extracted
    """

    firstname = person.firstname

    if firstname.endswith('.'):
        firstname = person.middlename
 
    if firstname_position == 'before':
        name = firstname + ' ' + person.lastname
    elif firstname_position == 'after':
        name = person.lastname + ', ' + firstname
    else:
        name = person.lastname
        
    if show_suffix:
        if person.namemod:
            name += ' ' + person.namemod
    
    if role_congress:
        role = person.get_last_role_at_congress(role_congress)
    elif role_date:
        role = person.get_role_at_date(role_date)
    elif role_year:
    	role = person.get_role_at_year(role_year)
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
 
    if show_party or show_district:
        name += ' ['
        if show_party:
            name += role.party[0] if role.party else '?'
        if show_party and show_district:
            name += '-'
        if show_district:
            name += role.state
            if role.role_type == RoleType.representative:
                name += str(role.district)
                
        if role_recent and not role.current:
        	a, b = role.logical_dates()
        	name += ", %d-%d" % (a.year, b.year)
        	
        name += ']'
                 
    return name
