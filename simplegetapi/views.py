from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, Http404
from django.db.models import Model
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.related import RelatedObject
from django.shortcuts import get_object_or_404
from django.conf import settings
from common import enum as enummodule
import csv, json, StringIO, datetime, lxml

def do_api_call(request, model, qs, id):
    """Processes an API request for a given ORM model, queryset, and optional ORM instance ID."""

    # Sanity checks.

    if type(qs).__name__ not in ("QuerySet", "SearchQuerySet"):
        raise Exception("Invalid use. Pass a QuerySet or Haystack SearchQuerySet.")

    if request.method != "GET":
        # This is a GET-only API.
        return HttpResponseNotAllowed(["GET"])
    
    # Get model information specifying how to format API results for calls rooted on this model.
    recurse_on = getattr(model, "api_recurse_on", [])
    recurse_on_single = getattr(model, "api_recurse_on_single", [])
    
    # The user can specify which fields he wants as a comma-separated list. Also supports
    # field__field chaining for related objects.
    requested_fields = [f.strip() for f in request.GET.get("fields", "").split(',') if f.strip() != ""]
    if len(requested_fields) == 0: requested_fields = None
    
    # Process the call.
    if id == None:
        response = do_api_search(request, model, qs, recurse_on, requested_fields)
    else:
        response = do_api_get_object(model, id, list(recurse_on) + list(recurse_on_single), requested_fields)
        
    # Return the result immediately if it is an error condition.
    if isinstance(response, HttpResponse):
        return response
        
    # Add some debugging info to output.
    if settings.DEBUG:
        from django.db import connections
        sqls = { }
        if "meta" in response:
            response["meta"]["sql_debug"] = sqls
        else:
            response["_sql_debug"] = sqls
        for con in connections:
            sqls[con] = connections[con].queries

    # Return results.
    format = request.GET.get('format', 'json')
    if format == "json":
        return serialize_response_json(response)
        
    elif format == "xml":
        return serialize_response_xml(response)
        
    elif format == "csv":
        return serialize_response_csv(response, id == None, requested_fields)
        
    else:
        return HttpResponseBadRequest("Invalid response format: %s." % format)
        
def is_enum(obj):
    import inspect
    return inspect.isclass(obj) and issubclass(obj, enummodule.Enum)

def serialize_object(obj, recurse_on=[], requested_fields=None):
    """Serializes a Python object to JSON-able data types (listed in the 1st if block below)."""
    
    if isinstance(obj, (str, unicode, int, long, float, list, tuple, dict)) or obj is None:
        # basic data type
        return obj
        
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        # dates and datetimes
        return obj.isoformat()
        
    elif isinstance(obj, Model):
        # ORM instances
        
        ret = { }
        
        # If requested_fields is set, get the list of fields to actually pull data from.
        # requested_fields supports field__field chaining, so just take the first part
        # of each specified field.
        local_fields = [f.split("__", 1)[0] for f in requested_fields] if requested_fields is not None else None
        
        # Loop through the fields on this model. Be sure to process only
        # fields that will not cause additional database queries. ForeignKey,
        # ManyToMany and those sorts of fields should be specified in a
        # recurse_on setting so that they go into the prefetch list.
        for field in obj._meta.fields + obj._meta.many_to_many + obj._meta.get_all_related_objects() + list(getattr(obj, "api_additional_fields", {})):
            # Get the field name.
            if isinstance(field, (str, unicode)):
                # for api_additional_fields
                field_name = field
            elif isinstance(field, RelatedObject):
                # for get_all_related_objects()
                field_name = field.get_accessor_name()
            else:
                # for other fields
                field_name = field.name

            # Is the user requesting particular fields? If so, check that this is a requested field.
            if local_fields is not None and field_name not in local_fields:
                continue
                
            # Don't recurse on models except where explicitly allowed. And if we aren't going to
            # recurse on this field, stop here so we don't incur a database lookup.
            #
            # For ForeignKeys, instead output the object ID value instead (which the ORM has already
            # cached).
            #
            # RelatedObject fields are reverse-relations, so we don't have the ID. Just skip
            # those.
            #
            # Other relation fields don't do a query when we access the attribute, so it is safe
            # to check those later. Those return RelatedManagers. We check those later.
            if isinstance(field, ForeignKey) and field_name not in recurse_on:
                ret[field_name] = getattr(obj, field_name + "_id")
                continue
            if isinstance(field, RelatedObject) and field_name not in recurse_on:
                continue
                
            # Get the field value.
            if not isinstance(field, (str, unicode)):
                # for standard fields
                try:
                    v = getattr(obj, field_name)
                except:
                    # some fields like OneToOne fields raise a DoesNotExist here
                    # if there is no related object.
                    v = None
            else:
                # for api_additional_fields
                v = obj.api_additional_fields[field] # get the attribute or function
                if not callable(v):
                    # it's an attribute name, so pull the value from the attribute
                    v = getattr(obj, v)
                    if callable(v):
                        # it's a bound method on the object, so call it to get the value
                        v = v()
                else:
                    # the value is a function itself, so call it passing the object instance
                    v = v(obj)
            
            # When serializing inside objects, if we have a field_name__subfield
            # entry in recurse_on, pass subfield to the inside serialization.
            sub_recurse_on = [r[len(field_name)+2:] for r in recurse_on if r.startswith(field_name + "__")]

            # Likewise for user-specified fields in requested_fields.
            sub_fields = [r[len(field_name)+2:] for r in requested_fields if r.startswith(field_name + "__")] if requested_fields is not None else None

            # Get the choices for the field, if there are any.
            choices = getattr(field, "choices", None)

            # For ManyToMany-type fields, serialize the related objects into a list.
            if isinstance(field, ManyToManyField) or str(type(v)) == "<class 'django.db.models.fields.related.RelatedManager'>":
                # Now that we know this is a related field, check that we are allowed to recurse
                # into it. If not, just skip the field entirely. Since we might have an unbounded
                # list of related objects, it is a bad idea to include even the IDs of the objects
                # unless the model author says that is OK.
                if field_name in recurse_on:
                    ret[field_name] = [serialize_object(vv, recurse_on=sub_recurse_on, requested_fields=sub_fields) for vv in v.all()]
                
            # For enumerations, output the key and label and not the raw database value.
            elif v is not None and is_enum(choices):
                v = choices.by_value(v)
                ret[field_name] = v.key
                ret[field_name + "_label"] = v.label
                
            # For all other values, serialize by recursion.
            else:
                ret[field_name] = serialize_object(v, recurse_on=sub_recurse_on, requested_fields=sub_fields)
        return ret
        
    # For all other object types, convert to unicode.
    else:
        return unicode(obj)
            

def do_api_search(request, model, qs, recurse_on, requested_fields):
    """Processes an API call search request, i.e. /api/modelname?..."""
    
    # Apply filters specified in the query string.

    qs_sort = None
    qs_filters = { }

    for arg, vals in request.GET.iterlists():
        if arg in ("offset", "limit", "format", "fields"):
            # These aren't filters.
            pass
        
        elif arg in ("sort", "order_by"):
            # ?sort=fieldname or ?sort=-fieldname
            
            if len(vals) != 1:
                return HttpResponseBadRequest("Invalid query: Multiple sort parameters.")
                
            try:
                qs = qs.order_by(vals[0]) # fieldname or -fieldname
            except Exception as e:
                return HttpResponseBadRequest("Invalid sort: %s" % repr(e))

            qs_sort = (vals[0], "+")
            if vals[0].startswith("-"): qs_sort = (vals[0][1:], "-")

        elif arg == "q" and type(qs).__name__ == "SearchQuerySet":
            # For Haystack searches, 'q' is a shortcut for the content= filter which
            # does Haystack's full text search.
            
            if len(vals) != 1:
                return HttpResponseBadRequest("Invalid query: Multiple %s parameters." % arg)
            qs = qs.filter(content=vals[0])

        else:
            # This is a regular field filter.
            
            # split fieldname__operator into parts
            arg_parts = arg.rsplit("__", 1) # (field name, ) or (field name, operator)
            
            if len(vals) > 1:
                # If the filter argument is specified more than once, Django gives us the values
                # as an array in vals. When used this way, force the __in operator and don't let
                # the user specify it explicitly.
                arg_parts[0] = arg
                arg_parts[1] = "in"
                
            elif len(arg_parts) == 2 and arg_parts[1] not in ("contains", "exact", "gt", "gte", "lt", "lte", "in", "startswith", "range"):
                # If the operator isn't actually an operator, it's a sub-field name and the user
                # wants the implicit __exact operator.
                # e.g. field1__field2 means ('field1__field12', 'exact')
                arg_parts[0] += "__" + arg_parts[1]
                arg_parts.pop()
                
            # If there's no __ in the field name (or we adjusted it above), add the implicit __exact operator.
            if len(arg_parts) == 1: arg_parts.append("exact") # default operator
            fieldname, matchoperator = arg_parts
            
            # Get the model field. For Haystack queries, this filter may not correspond to a model field.
            try:
                modelfield = model._meta.get_field(fieldname)
            except:
                modelfield = None
            
            # Handle enum fields in a special way.
            try:
                choices = modelfield.choices
                if is_enum(choices):
                    # Allow the | as a separator to accept multiple values (unless the field was specified
                    # multiple times as query parameters).
                    if len(vals) == 1: vals = vals[0].split("|")
                    
                    # Convert the string value to the raw database integer value.
                    vals = [int(choices.by_key(v)) for v in vals]
            except: # field is not a model field, or enum value is invalid (leave as original)
                pass
                
            try:
                if matchoperator not in ("in", "range"):
                    # Single-value operators.
                    qs = qs.filter(**{ fieldname + "__" + matchoperator: vals[0] })
                else:
                    # Multi-value operators.
                    qs = qs.filter(**{ fieldname + "__" + matchoperator: vals })
            except Exception as e:
                return HttpResponseBadRequest("Invalid filter: %s" % repr(e))
                
            qs_filters[fieldname] = (matchoperator, modelfield)
    
    
    # Is this a valid set of filters and sort option?

    if type(qs).__name__ == "QuerySet":
        # The queryset is a Django ORM QuerySet. Allow filtering/sorting on all Django ORM fields
        # with db_index=True. Additionally allow filtering on a prefix of any Meta.unqiue.
        
        # Get the fields with db_index=True. The id field is implicitly indexed.
        indexed_fields = set(f.name for f in model._meta.fields if f.name == 'id' or f.db_index)

        # For every (a,b,c) in unique_together, make a mapping like:
        #  a: [] # no dependencies, but indexed
        #  b: a
        #  c: (a,b)
        # indicating which other fields must be filtered on to filter one of these fields.
        indexed_if = { }
        for unique_together in model._meta.unique_together:
            for i in xrange(len(unique_together)):
                indexed_if[unique_together[i]] = unique_together[:i]
        
        # Check the sort field is OK.
        if qs_sort and qs_sort[0] not in indexed_fields:
            return HttpResponseBadRequest("Cannot sort on field: %s" % fieldname)
            
        # Check the filters are OK.
        for fieldname, (modelfield, operator) in qs_filters.items():
            if fieldname not in indexed_fields and fieldname not in indexed_if:
                return HttpResponseBadRequest("Cannot filter on field: %s" % fieldname)                
            
            for f2 in indexed_if.get(fieldname, []):
                if f2 not in qs_filters:
                    return HttpResponseBadRequest("Cannot filter on field %s without also filtering on %s" %
                        (fieldname, ", ".join(indexed_if[fieldname])))
        
        # Don't allow very high offset values because MySQL fumbles the query optimization.
        allow_large_offset = False
        
    elif type(qs).__name__ == "SearchQuerySet":
        # The queryset is a Haystack SearchQuerySet. Allow filtering/sorting on fields indexed
        # in Haystack, as specified in the haystack_index attribute on the model (a tuple/list)
        # and the haystack_index_extra attribute which is a tuple/list of tuples, the first
        # element of which is the Haystack field name.
        indexed_fields = set(getattr(model, "haystack_index", [])) | set(f[0] for f in getattr(model, "haystack_index_extra", []))
        
        # Check the sort field is OK.
        if qs_sort and qs_sort[0] not in indexed_fields:
            return HttpResponseBadRequest("Cannot sort on field: %s" % fieldname)
            
        # Check the filters are OK.
        for fieldname, (modelfield, operator) in qs_filters.items():
            if fieldname not in indexed_fields:
                return HttpResponseBadRequest("Cannot filter on field: %s" % fieldname)
            
        allow_large_offset = True
        
    # Form the response.

    # Get total count before applying offset/limit.
    count = qs.count()

    # Apply offset/limit.
    try:
        offset = int(request.GET.get("offset", "0"))
        limit = int(request.GET.get("limit", "100"))
        qs = qs[offset:offset + limit]
    except ValueError:
        return HttpResponseBadRequest("Invalid offset or limit.")
        
    if offset > 10000 and not allow_large_offset:
        return HttpResponseBadRequest("Offset > 10000 is not supported for this data type. Try a __gt filter instead.")
        
    # Bulk-load w/ prefetch_related, but keep order.
    
    if type(qs).__name__ == "QuerySet":
        # For Django ORM QuerySets, just add prefetch_related based on the fields
        # we're allowed to recurse inside of.
        objs = qs.prefetch_related(*recurse_on) 
    elif type(qs).__name__ == "SearchQuerySet":
        # For Haystack SearchQuerySets, we need to get the ORM instance IDs,
        # pull the objects in bulk, and then sort by the original return order.
        ids = [entry.pk for entry in qs]
        id_index = { int(id): i for i, id in enumerate(ids) }
        objs = list(model.objects.filter(id__in=ids).prefetch_related(*recurse_on))
        objs.sort(key = lambda ob : id_index[int(ob.id)])

    # Serialize.
    return {
        "meta": {
            "offset": offset,
            "limit": limit,
            "total_count": count,
        },
        "objects": [serialize_object(s, recurse_on=recurse_on, requested_fields=requested_fields) for s in objs],
    }

def do_api_get_object(model, id, recurse_on, requested_fields):
    """Gets a single object by primary key."""
    
    # Object ID is known.
    obj = get_object_or_404(model, id=id)
    
    # Serialize.
    return serialize_object(obj, recurse_on=recurse_on, requested_fields=requested_fields)

def serialize_response_json(response):
    """Convert the response dict to JSON."""
    ret = json.dumps(response, sort_keys=True, ensure_ascii=False, indent=True)
    resp = HttpResponse(ret, mimetype="application/json")
    resp["Content-Length"] = len(ret)
    return resp

def serialize_response_xml(response):
    """Convert the response dict to XML."""
    
    def make_node(parent, obj):
        if isinstance(obj, (str, unicode)):
            parent.text = obj
        elif isinstance(obj, (int, long, float)):
            parent.text = unicode(obj)
        elif obj is None:
            parent.text = "null"
        elif isinstance(obj, (list, tuple)):
            for n in obj:
                m = lxml.etree.Element("item")
                parent.append(m)
                make_node(m, n)
        elif isinstance(obj, dict):
            for key, val in sorted(obj.items(), key=lambda kv : kv[0]):
                n = lxml.etree.Element(key)
                parent.append(n)
                make_node(n, val)
        else:
            raise ValueError("Unhandled data type in XML serialization: %s" % unicode(type(obj)))
    
    root = lxml.etree.Element("response")
    make_node(root, response)
    
    ret = lxml.etree.tostring(root, encoding="utf8", pretty_print=True)
    resp = HttpResponse(ret, mimetype="text/xml")
    resp["Content-Length"] = len(ret)
    return resp
    
def serialize_response_csv(response, is_list, requested_fields):
    if is_list:
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
    if len(raw_data) > 500000:
        resp['Content-Disposition'] = 'attachment; filename="query.csv"'
    else:
        resp['Content-Disposition'] = 'inline; filename="query.csv"'
    return resp

