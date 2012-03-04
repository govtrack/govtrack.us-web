from django import forms
from django.utils.safestring import mark_safe
from django.contrib.humanize.templatetags.humanize import ordinal

from smartsearch.manager import SearchManager

from person.models import Person, PersonRole
from person.types import RoleType
from name import get_person_name
from us import statenames

import os.path

years = [(x, str(x)) for x in xrange(2011, 1788, -1)]

def name_filter(qs, form):
    name = form["name"]
    if name.strip() != "":
        qs = qs.filter(lastname__startswith=name.strip())
    return qs

def year_filter(qs, form):
    year = form['roles__year']
    if year != '':
        qs = qs.filter(roles__startdate__lte=("%d-12-31"%int(year)), roles__enddate__gte=("%d-01-01"%int(year)))
    return qs
    
def current_filter(qs, form):
    # since individuals can have both current and non-current roles, the
    # right way to filter when current is false is to exclude anyone
    # with a current role, not to find roles that are not-current.
    if not "roles__current" in form:
        return qs
    elif form["roles__current"] == "true":
        qs = qs.filter(roles__current=True)
    elif form["roles__current"] == "false":
        qs = qs.exclude(roles__current=True)
    return qs
    
def sort_filter(qs, form):
    if form["sort"] == 'name':
        qs = qs.order_by('lastname', 'firstname')
    if form["sort"] == 'district':
        qs = qs.order_by('roles__state', 'roles__district', 'roles__startdate', 'lastname', 'firstname')
    return qs

def cell_content(obj, form):
    return obj.name_no_details_lastfirst()

def left_content(obj, form):
    if not os.path.exists("data/photos/%d.jpeg" % obj.id): return mark_safe("<div style=\"border: 1px solid black; width: 50px; height: 60px;\"/>")
    return mark_safe("<img src=\"/data/photos/%d-50px.jpeg\" width=\"50\" height=\"60\"/>" % obj.id)
        
def bottom_content(obj, form):
    try:
        if "roles__year" in form:
            return obj.get_role_at_year(int(form["roles__year"])).get_description()
        elif form.get("roles__current", "__ALL__") == "true":
            return obj.get_current_role().get_description()
        else:
            role = obj.get_most_recent_role()
            a, b = role.logical_dates()
            return role.get_description() + ", %d-%d" % (a.year, b.year)
    except Exception as e:
        return ""

def person_search_manager():
    sm = SearchManager(Person) #, qs=Person.objects.filter(roles__role_type__in=(RoleType.representative, RoleType.senator))) # make sure person has a role, and is not a president
    
    sm.add_option('text', label='name', type="text")
    sm.add_option('is_currently_serving', label="currently serving?", type="radio", choices=[(False, "No"), (True, "Yes")])
    sm.add_option('most_recent_role_type', label="senator or representative", type="radio", formatter = lambda v : v.capitalize())
    sm.add_option('most_recent_role_state', label="state", type="select", formatter = lambda state : statenames[state.upper()], sort="LABEL")
    sm.add_option('most_recent_role_district', label="district", type="select", formatter = lambda v : "At Large" if v == 0 else ordinal(v), visible_if=lambda form:"most_recent_role_state" in form, sort="KEY")
    sm.add_option('most_recent_role_party', label="party", type="select", formatter = lambda v : v.capitalize())
    sm.add_option('gender')
    
    # sm.add_option('name', label='last name', type="text", filter=name_filter, choices="NONE")
    # sm.add_option('roles__current', label="currently serving?", type="radio", filter=current_filter)
    # sm.add_option('roles__year', label="year served", type="select", visible_if=lambda form : form.get("roles__current", "__ALL__") == "false", filter=year_filter, choices=years)
    # sm.add_option('roles__role_type', label="chamber")
    # sm.add_option('roles__state', label='state', sort=False, type="select")
    # sm.add_option('roles__district', label='district', sort=False, choices=[('0', 'At Large')] + [(x, str(x)) for x in xrange(1, 53+1)], type="select", visible_if=lambda form : form.get("roles__state", "__ALL__") != "__ALL__" and unicode(RoleType.representative) in form.getlist("roles__role_type[]"))
    # sm.add_option('roles__party', label='party', type="select")
    # sm.add_option('gender')
    # sm.add_option('sort', label='sort by', choices=[('name', 'name'), ('district', 'state/district, then year')], filter=sort_filter, type="radio", required=True)
    
    sm.add_column("Name", cell_content)
    sm.add_bottom_column(bottom_content)
    sm.add_left_column("", left_content)

    return sm
    

