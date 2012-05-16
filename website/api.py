from django.core.serializers import json as django_json
from django.utils import simplejson
from tastypie.serializers import Serializer
from tastypie.resources import ModelResource
from tastypie.api import Api
from tastypie import fields
from tastypie.constants import ALL, ALL_WITH_RELATIONS

from common import enum as enummodule

import json

class PrettyJSONSerializer(Serializer):
    json_indent = 2

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        return simplejson.dumps(data, cls=django_json.DjangoJSONEncoder,
                sort_keys=True, ensure_ascii=False, indent=self.json_indent)
        
class GBaseModel(ModelResource):
	
	# Base options.
	class BaseMeta:
		allowed_methods = ['get']
		serializer = PrettyJSONSerializer() # Override to make JSON output pretty.
		
	def determine_format(self, request):
		# Make JSON the default output format if not specified.
		if not hasattr(request, 'format'):
			return "application/json"
		return super(UserResource, self).determine_format(request)
	
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
				enum = bundle.obj._meta.get_field(field).choices
				if issubclass(enum, enummodule.Enum):
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
					info["values"] = dict((v.key, { "label": v.label } ) for v in enum.values())
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

from person.models import Person, PersonRole
class PersonModel(GBaseModel):
	class Meta(GBaseModel.BaseMeta):
		queryset = Person.objects.all()
		resource_name = 'person'
		filtering = {
			"firstname": ('exact,'),
			"gender": ALL,
			"lastname": ('exact,'),
			"metavidid": ALL,
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
			"name": "name",
			"name_no_details": "name_no_details",
			"name_sortable": "sortname",
			"link": lambda obj : "http://www.govtrack.us" + obj.get_absolute_url(),
		}
	roles = fields.ToManyField('website.api.PersonRoleModel', 'roles')
	current_role = fields.ToOneField('website.api.PersonRoleModel', 'current_role', null=True, full=True)
	
class PersonRoleModel(GBaseModel):
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
		additional_properties = {
			"title": "get_title_abbreviated",
			"title_long": "get_title",
			"description": "get_description",
		}
	
from bill.models import Bill
class BillModel(GBaseModel):
	class Meta(GBaseModel.BaseMeta):
		queryset = Bill.objects.all()
		resource_name = 'bill'
		filtering = {
			"bill_type": ('exact',),
			"congress": ALL,
			"number": ALL,
			"sponsor": ALL_WITH_RELATIONS,
			"committees": ALL_WITH_RELATIONS,
			"terms": ALL_WITH_RELATIONS,
			"current_status": ALL,
			"current_status_date": ALL,
			"introduced_date": ALL,
			"cosponsors": ALL_WITH_RELATIONS,
			"docs_house_gov_postdate": ALL,
			"senate_floor_schedule_postdate": ALL,
		}
		excludes = ["titles", "major_actions"]
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
	sponsor = fields.ToOneField('website.api.PersonModel', 'sponsor', null=True, full=True)
	cosponsors = fields.ToManyField('website.api.PersonModel', 'cosponsors')
	# missing: terms, committees


v1_api = Api(api_name='v1')

v1_api.register(PersonModel())
v1_api.register(PersonRoleModel())
v1_api.register(BillModel())

