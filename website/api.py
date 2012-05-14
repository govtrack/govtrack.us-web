from django.core.serializers import json as django_json
from django.utils import simplejson
from tastypie.serializers import Serializer
from tastypie.resources import ModelResource
from tastypie.api import Api
from tastypie import fields
from tastypie.constants import ALL, ALL_WITH_RELATIONS

import json

class PrettyJSONSerializer(Serializer):
    json_indent = 2

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        return simplejson.dumps(data, cls=django_json.DjangoJSONEncoder,
                sort_keys=True, ensure_ascii=False, indent=self.json_indent)
        
class GBaseModel(ModelResource):
	class BaseMeta:
		allowed_methods = ['get']
		serializer = PrettyJSONSerializer() # Override to make JSON output pretty.
	def determine_format(self, request):
		# Make JSON the default output format if not specified.
		if not hasattr(request, 'format'):
			return "application/json"
		return super(UserResource, self).determine_format(request)
	
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
	sponsor = fields.ToOneField('website.api.PersonModel', 'sponsor', null=True, full=True)
	cosponsors = fields.ToManyField('website.api.PersonModel', 'cosponsors')
	# missing: terms

v1_api = Api(api_name='v1')

v1_api.register(PersonModel())
v1_api.register(PersonRoleModel())
v1_api.register(BillModel())

