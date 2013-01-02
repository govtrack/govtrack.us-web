from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, Http404
from django.db.models import Model
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.related import RelatedObject
from django.shortcuts import get_object_or_404
from django.conf import settings
from common import enum as enummodule
import csv, json, StringIO, datetime

def is_enum(obj):
	import inspect
	return inspect.isclass(obj) and issubclass(obj, enummodule.Enum)

def serialize(obj, recurse_on=[], requested_fields=None):
	if isinstance(obj, (str, unicode, int, float, list, tuple, dict)) or obj is None:
		return obj
	elif isinstance(obj, list):
		return [serialize(s, requested_fields=requested_fields) for s in obj]
	elif isinstance(obj, (datetime.date, datetime.datetime)):
		return obj.isoformat()
	elif isinstance(obj, Model):
		# For fields with __ chaining, just get the first part.
		local_fields = [f.split("__", 1)[0] for f in requested_fields] if requested_fields is not None else None
		
		# Loop through the fields on this model. Be sure to process only
		# fields that will not cause additional database queries. ForeignKey,
		# ManyToMany and those sorts of fields should be specified in a
		# recurse_on setting so that they go into the prefetch list.
		ret = { }
		for field in obj._meta.fields + obj._meta.many_to_many + obj._meta.get_all_related_objects():
			# Get the field name.
			if isinstance(field, (str, unicode)): # for haystack_index_extra
				field_name = field
			elif isinstance(field, RelatedObject):
				field_name = field.get_accessor_name()
			else:
				field_name = field.name

			# Is the user requesting particular fields?
			if local_fields is not None and field_name not in local_fields:
				continue
				
			# Don't recurse on models except where explicitly allowed.
			# If we're not recursing, avoid making a database query
			# and access the _id field directly.
			if isinstance(field, ForeignKey) and field_name not in recurse_on:
				ret[field_name] = getattr(obj, field_name + "_id")
				continue
				
			# Get the field value.
			v = getattr(obj, field_name)
			if callable(v): v = v() # for haystack_index_extra fields, which are functions
			
			# When serializing inside objects, if we have a field_name__subfield
			# entry in recurse_on, pass subfield to the inside serialization.
			sub_recurse_on = [r[len(field_name)+2:] for r in recurse_on if r.startswith(field_name + "__")]

			# Likewise for user-pulled fields.
			sub_fields = [r[len(field_name)+2:] for r in requested_fields if r.startswith(field_name + "__")] if requested_fields is not None else None

			if isinstance(field, ManyToManyField) or str(type(v)) == "<class 'django.db.models.fields.related.RelatedManager'>":
				if field_name in recurse_on:
					ret[field_name] = [serialize(vv, recurse_on=sub_recurse_on, requested_fields=sub_fields) for vv in v.all()]
				#elif with_simple_m2ms:
				#	ret[field_name] = list(int(x) for x in v.all().values_list('id', flat=True))
				continue
				
			# For enumerations, output the key and label and not the integer value.
			choices = getattr(field, "choices", None)
			if v is not None and is_enum(choices):
				v = choices.by_value(v)
				ret[field_name] = v.key
				ret[field_name + "_label"] = v.label
				
			# Otherwise serialize the value.
			else:
				ret[field_name] = serialize(v, recurse_on=sub_recurse_on, requested_fields=sub_fields)
		return ret
	else:
		return unicode(obj)
			
def do_api_call(request, model, qs, id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])
	
	recurse_on = getattr(model, "api_recurse_on", [])
	recurse_on_single = getattr(model, "api_recurse_on_single", [])
	
	# get the requested fields, comma-separated __-chained field names
	requested_fields = [f.strip() for f in request.GET.get("fields", "").split(',') if f.strip() != ""]
	if len(requested_fields) == 0: requested_fields = None
	
	if id == None:
		# DO A SEARCH

		# Apply filters.
		
		if type(qs).__name__ == "QuerySet":
			# Allow filtering on all Django ORM fields since we don't know what
			# is efficient and what isn't. db_index on the field helps, but
			# complex indices in the database makes this hard to do.
			#fields = [f.name for f in model._meta.fields if f.name == 'id' or f.db_index]
			fields = getattr(model, "api_allowed_filters", None)
			if fields is not None: fields = set(fields)
			def is_filterable_field(f): return fields is None or f in fields
			is_sortable_field = is_filterable_field
		else:
			# Allow filtering on fields indexed in Haystack.
			fields = set(getattr(model, "haystack_index", [])) | set(f[0] for f in getattr(model, "haystack_index_extra", []))
			def is_filterable_field(f): return f in fields
			def is_sortable_field(f): return f in fields
		
		for arg, vals in request.GET.iterlists():
			if arg in ("offset", "limit", "format", "fields"):
				pass
			
			elif arg == "sort":
				if len(vals) != 1:
					return HttpResponseBadRequest("Invalid query: Multiple sort parameters.")
					
				fieldname = vals[0]
				if fieldname.startswith("-"): fieldname = fieldname[1:]
				if not is_sortable_field(fieldname):
					return HttpResponseBadRequest("Invalid sort field: %s" % fieldname)
					
				qs = qs.order_by(vals[0]) # fieldname or -fieldname

			elif arg == "q":
				if len(vals) != 1:
					return HttpResponseBadRequest("Invalid query: Multiple %d parameters." % fieldname)
				qs = qs.filter(content=vals[0])

			else:
				# split fieldname__operator into parts
				arg_parts = arg.rsplit("__", 1)
				
				if len(arg_parts) == 2 and arg_parts[1]	not in ("contains", "exact", "gt", "gte", "lt", "lte", "in", "startswith", "range"):
					# e.g. field1__field2 => ('field1__field12', 'exact')
					arg_parts[0] += "__" + arg_parts[1]
					arg_parts.pop()
					
				if len(arg_parts) == 1: arg_parts.append("exact") # default operator
				fieldname, matchoperator = arg_parts
				
				if not is_filterable_field(fieldname):
					return HttpResponseBadRequest("Invalid field name: %s" % fieldname)
					
				# For enum fields, convert key to integer value.
				try:
					choices = model._meta.get_field(fieldname).choices
					if is_enum(choices):
						vals = [int(choices.by_key(v)) for v in vals]
				except: # field is not a model field, or enum value is invalid (leave as original)
					pass
					
				try:
					if matchoperator not in ("in", "range"):
						# Single-value operators.
						if len(vals) != 1:
							return HttpResponseBadRequest("Invalid query: Multiple %d parameters." % fieldname)
						qs = qs.filter(**{ fieldname + "__" + matchoperator: vals[0] })
					else:
						# Multi-value operators.
						qs = qs.filter(**{ fieldname + "__" + matchoperator: vals })
				except ValueError as e:
					return HttpResponseBadRequest("Invalid filter: %s" % repr(e))
		
		# Get total count before applying offset/limit.
		count = qs.count()
	
		# Apply offset/limit.
		try:
			offset = int(request.GET.get("offset", "0"))
			limit = int(request.GET.get("limit", "100"))
			qs = qs[offset:offset + limit]
		except ValueError:
			return HttpResponseBadRequest("Invalid offset or limit.")
			
		# Bulk-load w/ prefetch_related, and keep order.
		ids = [entry.pk for entry in qs]
		id_index = { int(id): i for i, id in enumerate(ids) }
		objs = list(model.objects.filter(id__in=ids).prefetch_related(*recurse_on))
		objs.sort(key = lambda ob : id_index[int(ob.id)])
	
		# Serialize.
		response = {
			"meta": {
				"offset": offset,
				"limit": limit,
				"total_count": count,
			},
			"objects": [serialize(s, recurse_on=recurse_on, requested_fields=requested_fields) for s in objs],
		}
		
	else:
		# GET A SINGLE OBJECT
		
		# Object ID is known.
		obj = get_object_or_404(model, id=id)
		
		# Serialize.
		response = serialize(obj, recurse_on=list(recurse_on) + list(recurse_on_single), requested_fields=requested_fields)
	
	# Return results.
	format = request.GET.get('format', 'json')
	if format == "json":
		if settings.DEBUG:
			from django.db import connections
			sqls = { }
			if "meta" in response:
				response["meta"]["sql_debug"] = sqls
			else:
				response["_sql_debug"] = sqls
			for con in connections:
				sqls[con] = connections[con].queries
		
		ret = json.dumps(response, sort_keys=True, ensure_ascii=False, indent=True)
		resp = HttpResponse(ret, mimetype="application/json")
		resp["Content-Length"] = len(ret)
		return resp
		
	elif format == "csv":
		if id == None:
			response = response["objects"]
		else:
			response = [response]
		
		if requested_fields is None:
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
			requested_fields = []
			for item in response:
				for key in get_keys(item, ""):
					if key not in requested_fields:
						requested_fields.append(key)
			requested_fields.sort()
					
		# write CSV to buffer
		raw_data = StringIO.StringIO()
		writer = csv.writer(raw_data)
		writer.writerow(requested_fields)
		def get_value_recursively(item, key):
			for k in key.split("__"):
				if not isinstance(item, dict): return None
				item = item.get(k, None)
			return item
		def format_value(v):
			if v != None: v = unicode(v).encode("utf8")
			return v
		for item in response:
			writer.writerow([format_value(get_value_recursively(item, c)) for c in requested_fields])
			
		raw_data = raw_data.getvalue()
		resp = HttpResponse(raw_data, mimetype="text/csv")
		resp["Content-Length"] = len(raw_data)
		return resp
		
	else:
		return HttpResponseBadRequest("Invalid response format: %s." % format)
		
