from django.core.serializers import json as django_json
from django.utils import simplejson
from tastypie.serializers import Serializer
from tastypie.resources import ModelResource
from tastypie.api import Api
from tastypie import fields
from tastypie.constants import ALL, ALL_WITH_RELATIONS

from common import enum as enummodule

import csv, json, StringIO

class MySerializer(Serializer):
    def __init__(self, *args, **kwargs):
        Serializer.__init__(self, *args, **kwargs)
        self.formats += ['csv', 'debug_sql']
        self.content_types['csv'] = 'text/csv'
        self.content_types['debug_sql'] = 'text/plain'
    
	# Make JSON output pretty.
    json_indent = 2
    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        return simplejson.dumps(data, cls=django_json.DjangoJSONEncoder,
                sort_keys=True, ensure_ascii=False, indent=self.json_indent)

    # CSV outputter.
    def to_csv(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        
        data = data.get("objects", [])
        
        # get an (ordered) list of column names from top-level keys, if
        # not specified
        if "columns" in options:
            # This doesn't work. options doesn't seem to have the
            # query string arguments.
            columns = options["columns"].split(",")
        else:
            # Recursively find all keys in the object, making keys like
            # a__b when we dive into dicts within dicts.
            def get_keys(obj, prefix):
                ret = []
                for key in obj.keys():
                    if not isinstance(obj[key], dict):
                        ret.append(prefix + key)
                    else:
                        for inkey in get_keys(obj[key], prefix + key + "__"):
                            ret.append(inkey)
                return ret
            columns = []
            for item in data:
                for key in get_keys(item, ""):
                    if key not in columns:
                        columns.append(key)
            columns.sort()
                    
        # write CSV to buffer
        raw_data = StringIO.StringIO()
        writer = csv.writer(raw_data)
        writer.writerow(columns)
        def get_value_recursively(item, key):
            for k in key.split("__"):
                if not isinstance(item, dict): return None
                item = item.get(k, None)
            return item
        def format_value(v):
            if v != None: v = unicode(v).encode("utf8")
            return v
        for item in data:
            if not isinstance(item, dict): continue
            writer.writerow([format_value(get_value_recursively(item, c)) for c in columns])
            
        return raw_data.getvalue()

    def to_debug_sql(self, data, options=None):
        ret = StringIO.StringIO()
        ret.write("connection\ttime\tquery\n")
        from django.db import connections
        for con in connections:
            for q in connections[con].queries:
                ret.write("%s\t%s\t%s\n" % (con, q["time"], q["sql"]))
        return ret.getvalue()
    	
class GBaseModel(ModelResource):
	
	# Base options.
	class BaseMeta:
		allowed_methods = ['get']
		serializer = MySerializer()
		
	def determine_format(self, request):
		# Make JSON the default output format if not specified.
		if not hasattr(request, 'format') and "format" not in request.GET:
			return "application/json"
		return super(GBaseModel, self).determine_format(request)
	
	def find_field(self, path):
		from tastypie.fields import RelatedField
		if len(path) == 0: raise ValueError("No field specified.") 
		if not path[0] in self.fields: return None, None #raise ValueError("Invalid field '%s' on model '%s'." % (path[0], self.Meta.queryset.model))
		field = self.fields[path[0]]
		if len(path) == 1:
			return (self, field.attribute)
		if not isinstance(field, RelatedField):
			return None, None
			#raise ValueError("Trying to span a relationship that cannot be spanned ('%s')." % (path[0] + LOOKUP_SEP + path[1]))
		if not isinstance(field.to_class(), GBaseModel):
			return None, None
		return field.to_class().find_field(path[1:]) 
	
	@staticmethod
	def is_enum(obj):
		import inspect
		return inspect.isclass(obj) and issubclass(obj, enummodule.Enum)
	
	def build_filters(self, filters=None):
		if not filters: return { }
		# Replace enumeration keys with the right values.
		from django.db.models.sql.constants import QUERY_TERMS, LOOKUP_SEP
		f = { }
		for k, v in filters.items():
			path = k.split(LOOKUP_SEP)
			if len(path) and path[-1] in QUERY_TERMS.keys(): path.pop()
			model, field = self.find_field(path)
			if model:
				enum = model.Meta.queryset.model._meta.get_field(field).choices
				if GBaseModel.is_enum(enum):
					v = int(enum.by_key(v))
			f[k] = v
		return super(GBaseModel, self).build_filters(filters=f)
	
	def dehydrate(self, bundle):
		# Add additional properties.
		for name, attr in getattr(self.__class__.Meta, "additional_properties", {}).items():
			if callable(attr):
				val = attr(bundle.obj)
			else:
				val = getattr(bundle.obj, attr)
				if callable(val): val = val()
			bundle.data[name] = val
		
		# Replace integer values with their enumeration keys.
		for field in list(bundle.data): # clone the keys before we change the dict
			try:
				enum = self.Meta.queryset.model._meta.get_field(self.fields[field].attribute).choices
				if GBaseModel.is_enum(enum):
					val = enum.by_value(bundle.data[field])
					bundle.data[field] = val.key
					bundle.data[field + "_label"] = val.label
			except:
				# Entry does not correspond to a field with choices.
				pass
		return bundle

	def build_schema(self):
		# Add enumeration values to schema output.
		model = self.Meta.queryset.model
		schema = super(GBaseModel, self).build_schema()
		for field, info in schema["fields"].items():
			try:
				enum = model._meta.get_field(field).choices
				if issubclass(enum, enummodule.Enum):
					info["enum_values"] = dict((v.key, { "label": v.label, "description": getattr(v, "search_help_text", None) } ) for v in enum.values())
			except:
				# Entry does not correspond to a field with choices.
				pass
			
		# Add additional properties fields.
		for name, attr in getattr(self.Meta, "additional_properties", {}).items():
			if not callable(attr):
				val = getattr(model, attr)
				if callable(val) or isinstance(val, property):
					schema["fields"][name] = {
						"help_text": getattr(val, "__doc__", None) 
					}
					
		if "link" in getattr(self.Meta, "additional_properties", {}):
			schema["fields"]["link"] = {
				"help_text": "The URL to the corresponding page on www.GovTrack.us for this resource.",
			}
			
		return schema
		
	@classmethod
	def get_docstring(self):
		return self.__doc__

from person.models import Person, PersonRole
class PersonModel(GBaseModel):
	"""Members of Congress and U.S. Presidents since the founding of the nation."""
	
	canonical_example = 400326
	
	class Meta(GBaseModel.BaseMeta):
		queryset = Person.objects.all()
		resource_name = 'person'
		filtering = {
			"firstname": ('exact,'),
			"gender": ALL,
			"lastname": ('exact,'),
			"middlename": ('exact,'),
			"namemod": ('exact,'),
			"nickname": ('exact,'),
			"osid": ALL,
			"pvsid": ALL,
			"twitterid": ('exact,'),
			"youtubeid": ('exact,'),
			"roles": ALL_WITH_RELATIONS,
		}
		additional_properties = {
			"name_no_details": "name_no_details",
			"link": lambda obj : "http://www.govtrack.us" + obj.get_absolute_url(),
		}
	roles = fields.ToManyField('website.api.PersonRoleModel', 'roles', help_text="A list of terms in Congress or as President that this person has been elected to. A list of API resources to query for more information.")
	current_role = fields.ToOneField('website.api.PersonRoleModel', 'current_role', null=True, full=True, help_text="The current term in Congress or as President that this person is currently serving, or null if none.")

class PersonModelSimple(PersonModel):
	# Based on the PersonModel, but avoid fields that require another database call.
	class Meta(PersonModel.Meta):
		additional_properties = {
			"link": lambda obj : "http://www.govtrack.us" + obj.get_absolute_url(),
		}
		excludes = ["roles", "current_role"]
	
class PersonRoleModel(GBaseModel):
	"""Terms held in office by Members of Congress and U.S. Presidents. Each term corresponds with an election, meaning each term in the House covers two years (one 'Congress'), as President four years, and in the Senate six years (three 'Congresses')."""
	
	class Meta(GBaseModel.BaseMeta):
		queryset = PersonRole.objects.all()
		resource_name = 'role'
		filtering = {
			"current": ALL,
			"district": ALL,
			"enddate": ALL,
			"party": ('exact',),
			"role_type": ALL,
			"senator_class": ALL,
			"startdate": ALL,
			"state": ('exact,'),
		}
		ordering = ['startdate', 'enddate']
		additional_properties = {
			"title": "get_title_abbreviated",
			"title_long": "get_title",
			"description": "get_description",
			"congress_numbers": "congress_numbers",
		}
	
from bill.models import Bill
class BillModel(GBaseModel):
	"""Bills and resolutions in the U.S. Congress since 1973 (the 93rd Congress)."""
	
	canonical_example = 76416
	
	class Meta(GBaseModel.BaseMeta):
		queryset = Bill.objects.all().prefetch_related("sponsor", "sponsor_role")
		resource_name = 'bill'
		filtering = {
			"bill_type": ('exact',),
			"congress": ALL,
			"number": ALL,
			"sponsor": ALL_WITH_RELATIONS,
			"sponsor_role": ALL_WITH_RELATIONS,
			"committees": ALL_WITH_RELATIONS,
			"terms": ALL_WITH_RELATIONS,
			"current_status": ALL,
			"current_status_date": ALL,
			"introduced_date": ALL,
			#"cosponsors": ALL_WITH_RELATIONS,
			"docs_house_gov_postdate": ALL,
			"senate_floor_schedule_postdate": ALL,
		}
		excludes = ["titles", "major_actions"]
		ordering = ['current_status_date', 'introduced_date', 'docs_house_gov_postdate', 'senate_floor_schedule_postdate']
		additional_properties = {
			"link": lambda obj : "http://www.govtrack.us" + obj.get_absolute_url(),
			"display_number": "display_number_no_congress_number",
			"title_without_number": "title_no_number",
			"bill_resolution_type": "noun",
			"current_status_description": "current_status_description",
			"is_current": "is_current",
			"is_alive": "is_alive",
			"thomas_link": "thomas_link",
		}
	sponsor = fields.ToOneField('website.api.PersonModelSimple', 'sponsor', null=True, full=True, help_text="The primary sponsor of the bill (optional).")
	sponsor_role = fields.ToOneField('website.api.PersonRoleModel', 'sponsor_role', null=True, full=True, help_text="The role of the primary sponsor of the bill at the time he/she introduced the bill (optional).")
	#cosponsors = fields.ToManyField('website.api.PersonModelSimple', 'cosponsors', help_text="A list of cosponsors of the bill. A list of API resources to query for more information.")
	# missing: terms, committees
 
from bill.models import Cosponsor
class BillCosponsorModel(GBaseModel):
	"""A (bill, person) pair indicating cosponsorship, with join and withdrawn dates."""
	
	canonical_example = 402
	
	class Meta(GBaseModel.BaseMeta):
		queryset = Cosponsor.objects.all().prefetch_related("bill", "person", "role", "bill__sponsor", "bill__sponsor_role")
		resource_name = 'cosponsorship'
		filtering = {
			"bill": ALL_WITH_RELATIONS,
			"cosponsor": ALL_WITH_RELATIONS,
			"cosponsor_role": ALL_WITH_RELATIONS,
		}
	bill = fields.ToOneField('website.api.BillModel', 'bill', full=True, help_text="The bill.")
	cosponsor = fields.ToOneField('website.api.PersonModelSimple', 'person', full=True, help_text="The cosponsor.")
	cosponsor_role = fields.ToOneField('website.api.PersonRoleModel', 'role', full=True, help_text="The role of the cosponsor at the time he/she became a cosponsor of the bill.")

from vote.models import Vote
class VoteModel(GBaseModel):
	"""Roll call votes in the U.S. Congress since 1789. How people voted is accessed through the Vote_voter API."""
	
	canonical_example = 1
	
	class Meta(GBaseModel.BaseMeta):
		queryset = Vote.objects.all().select_related('options')
		resource_name = 'vote'
		filtering = {
			"congress": ALL,
			"session": ALL,
			"chamber": ('exact',),
			"number": ALL,
			"created": ALL,
			"category": ('exact'),
			"related_bill": ALL_WITH_RELATIONS,
		}
		excludes = ["missing_data"]
		ordering = ['created']
		additional_properties = {
			"link": lambda obj : "http://www.govtrack.us" + obj.get_absolute_url(),
			"source_link": "get_source_link",
			"options": "get_options",
			#"voters": "get_voters",
		}
	related_bill = fields.ToOneField('website.api.BillModel', 'related_bill', null=True, full=True, help_text="A bill related to this vote (optional, and possibly present even if this is not a vote on the passage of the bill).")

from vote.models import Voter
class VoteVoterModel(GBaseModel):
	"""How people voted on roll call votes in the U.S. Congress since 1789. See the Vote API. Filter on the vote field to get the results of a particular vote."""
	
	canonical_example = 8248474
	
	class Meta(GBaseModel.BaseMeta):
		queryset = Voter.objects.all().select_related('vote', 'person', 'option')
		resource_name = 'vote_voter'
		filtering = {
			"vote": ALL_WITH_RELATIONS,
			"person": ALL_WITH_RELATIONS,
			"option": ('exact',),
			"created": ALL,
		}
		additional_properties = {
			"option": "get_option_key",
			"person_name": "person_name",
			"vote_description": "get_vote_name",
			"link": lambda obj : "http://www.govtrack.us" + obj.vote.get_absolute_url(),
		}
		ordering = ['created']
	vote = fields.ToOneField('website.api.VoteModel', 'vote', help_text="The vote that this was a part of.")
	person = fields.ToOneField('website.api.PersonModel', 'person', help_text="The person making this vote.", blank=True, null=True)
	
	def build_filters(self, filters=None):
		# So that we don't have to create a model for the options, we rewrite
		# the output "option" key with the option's... key. To make it filterable,
		# we have to do a rewrite on the other end (this part).
		extra_filters = { }
		if filters and "option" in filters:
			extra_filters["option__key"] = filters["option"]
			del filters["option"]
		orm_filters = super(VoteVoterModel, self).build_filters(filters=filters)
		orm_filters.update(extra_filters)
		return orm_filters

v1_api = Api(api_name='v1')

v1_api.register(PersonModel())
v1_api.register(PersonRoleModel())
v1_api.register(BillModel())
v1_api.register(BillCosponsorModel())
v1_api.register(VoteModel())
v1_api.register(VoteVoterModel())

from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
import urllib

def api_overview(request):
	baseurl = "http://%s/api/v1/" % request.META["HTTP_HOST"]
	
	def get_resources():
		# wrapped in a function so it is cachable at the template level
		resources = sorted(v1_api._registry.items())
		for ep, r in resources:
			r.example_content = r.dispatch_list(request, congress=112, current=True, roles__current=True, limit=1).content
			r.fields_list = sorted((k, k.replace("_", u"_\u00AD"), v) for (k, v) in r.build_schema()["fields"].items())
		return resources
	
	return render_to_response('website/developers/api.html', {
		"baseurl": baseurl,
		"api": get_resources,
		},
		RequestContext(request))

#### V2 ####

from simplegetapi.views import do_api_call

def get_haystack_query_set(model, connection):
	from haystack.query import SearchQuerySet
	return SearchQuerySet().using(connection).filter(indexed_model_name__in=[model.__name__])

def apiv2(request, model, id):
	if model == "bill":
		model = Bill
		qs = get_haystack_query_set(model, "bill")
	elif model == "person":
		model = Person
		qs = get_haystack_query_set(model, "person")
	elif model == "vote":
		model = Vote
		qs = Vote.objects.all()
	elif model == "voter":
		model = Voter
		qs = Voter.objects.all()
	else:
		raise Http404()
	
	return do_api_call(request, model, qs, id)
	
