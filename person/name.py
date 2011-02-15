from datetime import datetime

from person.models import RoleType

CONGRESS_DATES = {}

def parse_govtrack_date(d):
    try:
        return datetime.strptime(d, '%Y-%m-%dT%H:%M:%S-04:00')
    except ValueError:
        pass
    else:
        try:
            return datetime.strptime(d, '%Y-%m-%dT%H:%M:%S-05:00')
        except ValueError:
            pass
        else:
            return datetime.strptime(d, '%Y-%m-%d')


def get_congress_dates(congressnumber):
    if not CONGRESS_DATES:
        cd = {}
        for line in open_govtrack_file('us/sessions.tsv'):
            cn, sessionname, startdate, enddate = line.strip().split('\t')[0:4]
            if not '-' in startdate: # header
                continue
            cn = int(cn)
            if not cn in cd:
                cd[cn] = [parse_govtrack_date(startdate), None]
            cd[cn][1] = parse_govtrack_date(enddate)
        CONGRESS_DATES.update(cd)
    return CONGRESS_DATES[congressnumber]


def get_person_name(person, role_date=datetime.now(), role_congress=None, firstname_position=None,
                show_suffix=False, show_title=True, show_party=True, show_district=True):
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
    
    if not role_date and not role_congress:
        return name
       
    if role_congress:
        role = person.get_last_role_at_congress(role_congress)
    elif role_date:
        role = person.get_role_at_date(role_date)
        
    if role is None:
        return name
 
    if role.role_type == RoleType.president:
        return 'President ' + name
        
    if show_title:
        name = role.get_title_abbreviated() + ' ' + name
 
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
        name += ']'
                 
    return name
