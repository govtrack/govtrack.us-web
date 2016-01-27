from django import forms
from django.utils.safestring import mark_safe
from django.contrib.humanize.templatetags.humanize import ordinal
from django.template import Context

from smartsearch.manager import SearchManager

from person.models import Person, PersonRole
from person.types import RoleType
from name import get_person_name
from us import statenames

def template_get_context(obj, form):
    c = Context({ "object": obj, "form": form })
    try:
        role = obj.get_most_recent_role()
        a, b = role.logical_dates(round_end=True)
        c["description"] = role.get_description() + ", %d-%d" % (a.year, b.year)
    except Exception as e:
        pass
    return c

def format_state(state):
    return state.upper() + " " + statenames[state.upper()]

def format_district(v):
    return "At Large" if v == 0 else ordinal(v)

def format_statedistrict(statedist):
    try:
        state, dist = statedist.split("-")
        dist = int(dist)
        return state + " " + format_district(dist)
    except ValueError:
        return statedist

def person_search_manager(mode):
    sm = SearchManager(Person, connection="person")

    sm.add_option('text', label='name', type="text")

    if mode == "current":
        sm.add_filter('current_role_type__in', [RoleType.representative, RoleType.senator])
        sm.add_option('current_role_type', label="serving in the...", type="radio", formatter=lambda v : RoleType.by_value(v).congress_chamber_long)
        sm.add_option('current_role_title', label="title", type="radio")
        sm.add_option('current_role_state', label="state", type="select", formatter=format_state, sort="LABEL")
        sm.add_option('current_role_district', label="district", type="select", formatter=format_district, visible_if=lambda form:"current_role_state" in form, sort="KEY")
        sm.add_option('current_role_party', label="party", type="select", formatter=lambda v : v.capitalize())
    elif mode == "all":
        sm.add_filter('all_role_types__in', [RoleType.representative, RoleType.senator])
        sm.add_filter('all_role_states__in', list(statenames)) # only to filter the facet so an empty state value doesn't appear for MoCs that have also served as prez/vp
        sm.add_option('all_role_types', label="ever served in the...", type="radio", formatter=lambda v : getattr(RoleType.by_value(v), 'congress_chamber_long', RoleType.by_value(v).label))
        sm.add_option('all_role_states', label="ever represented...", type="select", formatter=format_state, sort="LABEL")
        sm.add_option('all_role_districts', label="district...", type="select", formatter=format_statedistrict, visible_if=lambda form:"all_role_states" in form, sort="KEY")
        sm.add_option('all_role_parties', label="party", type="select")

    sm.add_option('gender')

    sm.add_sort("Name", "sortname", default=True)
    if mode == "current":
        sm.add_sort("Seniority (Oldest First)", "first_took_office")
        sm.add_sort("Seniority (Newest Members First)", "-first_took_office")
    elif mode == "all":
        sm.add_sort("First Took Office (Oldest First)", "first_took_office")
        sm.add_sort("First Took Office (Newest First)", "-first_took_office")
        sm.add_sort("Left Office", "-left_office")
    
    sm.set_template("""
    	<div style="float: left; margin-right: 1.5em">
			{% if object.has_photo %}
				<img src="{{object.get_photo_url_50}}" width="50" height="60"/>
			{% else %}
				<div style="border: 1px solid black; width: 50px; height: 60px;"/>
			{% endif %}
		</div>
    	<a href="{{object.get_absolute_url}}" style="margin-top: 4px">{{object.name_no_details_lastfirst}}</a>
    	<div>{{description}}</div>
	""")
    sm.set_template_context_func(template_get_context)

    return sm
    

