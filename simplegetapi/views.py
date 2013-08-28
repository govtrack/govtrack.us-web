from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, Http404, QueryDict
from django.db.models import Model
from django.db.models import DateField, DateTimeField
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.related import RelatedObject
from django.shortcuts import get_object_or_404
from django.conf import settings
from common import enum as enummodule
import csv, json, StringIO, datetime, lxml, urllib
import dateutil

def do_api_call(request, model, qs, id):
    """Processes an API request for a given ORM model, queryset, and optional ORM instance ID."""

    # Sanity checks.

    if type(qs).__name__ not in ("QuerySet", "SearchQuerySet"):
        raise Exception("Invalid use. Pass a QuerySet or Haystack SearchQuerySet.")

    if request.method != "GET":
        # This is a GET-only API.
        return HttpResponseNotAllowed(["GET"])
    
    # The user can specify which fields he wants as a comma-separated list. Also supports
    # field__field chaining for related objects.
    requested_fields = [f.strip() for f in request.GET.get("fields", "").split(',') if f.strip() != ""]
    if len(requested_fields) == 0: requested_fields = None
    
    # Process the call.
    if id == None:
        response = do_api_search(model, qs, request.GET, requested_fields)
    else:
        response = do_api_get_object(model, id, requested_fields)
        
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
        
    elif format == "jsonp":
        return serialize_response_jsonp(response, request.GET.get("callback", "callback"))
        
    elif format == "xml":
        return serialize_response_xml(response)
        
    elif format in ("csv", "csv:attachment", "csv:inline"):
        return serialize_response_csv(response, id == None, requested_fields, format)
        
    else:
        return HttpResponseBadRequest("Invalid response format: %s." % format)
        
def is_enum(obj):
    import inspect
    return inspect.isclass(obj) and issubclass(obj, enummodule.Enum)
    
def get_orm_fields(obj):
    for field in obj._meta.fields + \
        obj._meta.many_to_many + \
        obj._meta.get_all_related_objects() + \
        list(getattr(obj, "api_additional_fields", {})):
            
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
    
        yield field_name, field

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
        for field_name, field in get_orm_fields(obj):
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
            

def do_api_search(model, qs, request_options, requested_fields):
    """Processes an API call search request, i.e. /api/modelname?..."""
    
    qs_type = type(qs).__name__
    
    # Get model information specifying how to format API results for calls rooted on this model.
    recurse_on = getattr(model, "api_recurse_on", [])

    # Apply filters specified in the query string.

    qs_sort = None
    qs_filters = { }

    for arg, vals in request_options.iterlists():
        if arg in ("offset", "limit", "format", "fields", "callback"):
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

        elif arg == "q" and qs_type == "SearchQuerySet":
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
                arg_parts = [arg, "in"]
                
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

            if matchoperator in ("in", "range"):
                # Allow the | as a separator to accept multiple values (unless the field was specified
                # multiple times as query parameters).
                if len(vals) == 1:
                    vals = vals[0].split("|")
                    
            try:
                vals = [normalize_field_value(v, model, modelfield) for v in vals]
            except ValueError as e:
                return HttpResponseBadRequest("Invalid value for %s filter: %s" % (fieldname, str(e)))
                
            try:
                if matchoperator not in ("in", "range"):
                    # Single-value operators.
                    qs = qs.filter(**{ fieldname + "__" + matchoperator: vals[0] })
                else:
                    # Multi-value operators.
                    if matchoperator == "range" and len(vals) != 2:
                        return HttpResponseBadRequest("The range operator requires the range to be specified as two values separated by a pipe character (e.g. 100|200).")
                    if matchoperator == "in" and len(vals) == 0:
                        return HttpResponseBadRequest("The in operator requires an argument.")
                    
                    qs = qs.filter(**{ fieldname + "__" + matchoperator: vals })
            except Exception as e:
                return HttpResponseBadRequest("Invalid value for %s filter: %s" % (fieldname, repr(e)))
                
            qs_filters[fieldname] = (matchoperator, modelfield)
    
    
    # Is this a valid set of filters and sort option?
    
    indexed_fields, indexed_if = get_model_filterable_fields(model, qs_type)

    # Check the sort field is OK.
    if qs_sort and qs_sort[0] not in indexed_fields:
        return HttpResponseBadRequest("Cannot sort on field: %s" % qs_sort[0])
        
    # Check the filters are OK.
    for fieldname, (modelfield, operator) in qs_filters.items():
        if fieldname not in indexed_fields and fieldname not in indexed_if:
            return HttpResponseBadRequest("Cannot filter on field: %s" % fieldname)                
        
        for f2 in indexed_if.get(fieldname, []):
            if f2 not in qs_filters:
                return HttpResponseBadRequest("Cannot filter on field %s without also filtering on %s" %
                    (fieldname, ", ".join(indexed_if[fieldname])))
        
    # Form the response.

    # Get total count before applying offset/limit.
    try:
        count = qs.count()
    except ValueError as e:
        return HttpResponseBadRequest("A parameter is invalid: %s" % str(e))
    except Exception as e:
        return HttpResponseBadRequest("Something is wrong with the query: %s" % repr(e))

    # Apply offset/limit.
    try:
        offset = int(request_options.get("offset", "0"))
        limit = int(request_options.get("limit", "100"))
    except ValueError:
        return HttpResponseBadRequest("Invalid offset or limit.")
        
    if limit > 600:
        return HttpResponseBadRequest("Limit > 600 is not supported. Consider using our bulk data instead.")

    if qs_type == "QuerySet":
        # Don't allow very high offset values because MySQL fumbles the query optimization.
        if offset > 10000:
            return HttpResponseBadRequest("Offset > 10000 is not supported for this data type. Try a __gt filter instead.")

    qs = qs[offset:offset + limit]

    # Bulk-load w/ prefetch_related, but keep order.
    
    if qs_type == "QuerySet":
        # For Django ORM QuerySets, just add prefetch_related based on the fields
        # we're allowed to recurse inside of.
        objs = qs.prefetch_related(*recurse_on) 
    elif qs_type == "SearchQuerySet":
        # For Haystack SearchQuerySets, we need to get the ORM instance IDs,
        # pull the objects in bulk, and then sort by the original return order.
        ids = [entry.pk for entry in qs]
        id_index = { int(id): i for i, id in enumerate(ids) }
        objs = list(model.objects.filter(id__in=ids).prefetch_related(*recurse_on))
        objs.sort(key = lambda ob : id_index[int(ob.id)])
    else:
        raise Exception(qs_type)

    # Serialize.
    return {
        "meta": {
            "offset": offset,
            "limit": limit,
            "total_count": count,
        },
        "objects": [serialize_object(s, recurse_on=recurse_on, requested_fields=requested_fields) for s in objs],
    }
 
def normalize_field_value(v, model, modelfield):
    # Convert "null" to None.
    if v.lower() == "null":
        if modelfield and not modelfield.null:
            raise ValueError("Field cannot be null.")
        return None
        
    # If the model field's choices is a common.enum.Enum instance,
    # then the filter specifies the enum key, which has to be
    # converted to an integer.
    choices = modelfield.choices if modelfield else None
    if choices and is_enum(choices):
        try:
            # Convert the string value to the raw database integer value.
            return int(choices.by_key(v))
        except: # field is not a model field, or enum value is invalid (leave as original)
            raise ValueError("%s is not a valid value; possibly values are %s" % (v, ", ".join(c.key for c in choices.values())))

    # If this is a filter on a datetime field, parse the date in ISO format
    # because that's how we serialize it. Normally you can just pass a string
    # value to .filter(). The conversion takes place in the backend. MySQL
    # will recognize ISO-like formats. But Haystack with Solr will only
    # recognize the Solr datetime format. So it's better to parse now and
    # pass a datetime instance.
    
    is_dt = False
    if modelfield and isinstance(modelfield, (DateField, DateTimeField)):
        is_dt = True
    # and for our way of specifying additional Haystack fields...
    for fieldname, fieldtype in getattr(model, "haystack_index_extra", []):
        if modelfield and fieldname == modelfield.name and fieldtype in ("Date", "DateTime"):
            is_dt = True
    if is_dt:
        # Let any ValueErrors percolate up.
        return dateutil.parser.parse(str(v), default=datetime.datetime.min, ignoretz=not settings.USE_TZ)
        
    return v

def get_model_filterable_fields(model, qs_type):
    if qs_type == "QuerySet":
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
        
    elif qs_type == "SearchQuerySet":
        # The queryset is a Haystack SearchQuerySet. Allow filtering/sorting on fields indexed
        # in Haystack, as specified in the haystack_index attribute on the model (a tuple/list)
        # and the haystack_index_extra attribute which is a tuple/list of tuples, the first
        # element of which is the Haystack field name.
        indexed_fields = set(getattr(model, "haystack_index", [])) | set(f[0] for f in getattr(model, "haystack_index_extra", []))
        
        indexed_if = { }
        
    else:
        raise Exception(qs_type)

    return indexed_fields, indexed_if

def do_api_get_object(model, id, requested_fields):
    """Gets a single object by primary key."""
    
    # Object ID is known.
    obj = get_object_or_404(model, id=id)

    # Get model information specifying how to format API results for calls rooted on this model.
    recurse_on = list(getattr(model, "api_recurse_on", []))
    recurse_on += list(getattr(model, "api_recurse_on_single", []))

    # Serialize.
    return serialize_object(obj, recurse_on=recurse_on, requested_fields=requested_fields)

def serialize_response_json(response):
    """Convert the response dict to JSON."""
    ret = json.dumps(response, sort_keys=True, ensure_ascii=False, indent=True)
    ret = ret.encode("utf8")
    resp = HttpResponse(ret, mimetype="application/json; charset=utf-8")
    resp["Content-Length"] = len(ret)
    return resp

def serialize_response_jsonp(response, callback_name):
    """Convert the response dict to JSON."""
    ret = callback_name + "("
    ret += json.dumps(response, sort_keys=True, ensure_ascii=False, indent=True)
    ret += ");"
    ret = ret.encode("utf8")
    resp = HttpResponse(ret, mimetype="application/javascript; charset=utf-8")
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
    
def serialize_response_csv(response, is_list, requested_fields, format):
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
    if (len(raw_data) > 500000 and format == "csv") or format == "csv:attachment":
        resp = HttpResponse(raw_data, mimetype="text/csv")
        resp['Content-Disposition'] = 'attachment; filename="query.csv"'
    elif format == "csv:inline":
        resp = HttpResponse(raw_data, mimetype="text/csv")
        resp['Content-Disposition'] = 'inline; filename="query.csv"'
    else:
        resp = HttpResponse(raw_data, mimetype="text/plain")
        resp['Content-Disposition'] = 'inline'
    resp["Content-Length"] = len(raw_data)
    return resp

def build_api_documentation(model, qs):
    indexed_fields, indexed_if = get_model_filterable_fields(model, type(qs).__name__)
    
    ex_id = getattr(model, "api_example_id", None)

    if ex_id:
        example_data = do_api_get_object(model, ex_id, None)
    else:
        qd = QueryDict("limit=5").copy()
        for k, v in getattr(model, "api_example_parameters", {}).items():
            qd[k] = v
        example_data = do_api_search(model, qs, qd, None)
    example_data = json.dumps(example_data, sort_keys=True, ensure_ascii=False, indent=4)

    recurse_on = set(getattr(model, "api_recurse_on", []))
    recurse_on_single = set(getattr(model, "api_recurse_on_single", []))
    
    fields_list = []
    for field_name, field in get_orm_fields(model):
        field_info = { }

        # Indexed?
        if field_name in indexed_fields:
            field_info["filterable"] = "Filterable with operators. Sortable."
        if field_name in indexed_if:
            if len(indexed_if[field_name]) == 0:
                field_info["filterable"] = "Filterable."
            else:
                field_info["filterable"] = "Filterable when also filtering on " + " and ".join(indexed_if[field_name]) + "."
                
        if isinstance(field, (str, unicode)):
            # for api_additional_fields
            v = model.api_additional_fields[field] # get the attribute or function
            if not callable(v):
                # it's an attribute name, so pull the value from the attribute,
                # which hopefully gives something with a docstring
                v = getattr(model, v)
                field_info["help_text"] = v.__doc__
            
        elif isinstance(field, RelatedObject):
            # for get_all_related_objects()
            if field_name not in (recurse_on|recurse_on_single): continue
            field_info["help_text"] = "A list of %s instances whose %s field is this object. Each instance is returned as a JSON dict (or equivalent in other output formats)." % (field.model.__name__, field.field.name)
            if field_name not in recurse_on:
                field_info["help_text"] += " Only returned in a single-object query."
            
        else:
            # for regular fields
            field_info["help_text"] = field.help_text

            if isinstance(field, ForeignKey):
                if field_name not in (recurse_on|recurse_on_single):
                    field_info["help_text"] += " Returned as an integer ID."
                else:
                    if field_name in recurse_on:
                        field_info["help_text"] += " The full object is included in the response as a JSON dict (or equivalent in other output formats)."
                    else:
                        field_info["help_text"] += " In a list/search query, only the id is returned. In a single-object query, the full object is included in the response as a JSON dict (or equivalent in other output formats)."
                    if "filterable" in field_info:
                        field_info["filterable"] += " When filtering, specify the integer ID of the target object."

            if isinstance(field, ManyToManyField):
                if field_name not in (recurse_on|recurse_on_single): continue
                field_info["help_text"] += " Returned as a list of JSON dicts (or equivalent in other output formats)."
                if field_name not in recurse_on:
                    field_info["help_text"] += " Only returned in a query for a single object."
                if "filterable" in field_info:
                    field_info["filterable"] += " When filtering, specify the ID of one target object to test if the target is among the values of this field."
                    
            # Except ManyToMany
            elif "filterable" in field_info and field.null:
                field_info["filterable"] += " To search for a null value, filter on the special string 'null'."

            # Choices?
            enum = field.choices
            if is_enum(enum):
                field_info["enum_values"] = dict((v.key, { "label": v.label, "description": getattr(v, "search_help_text", None) } ) for v in enum.values())

        # Stupid Django hard-coded text.
        field_info["help_text"] = field_info.get("help_text", "").replace('Hold down "Control", or "Command" on a Mac, to select more than one.', '')

        fields_list.append((field_name, field_info))
    
    fields_list.sort()
    
    if type(qs).__name__ == "SearchQuerySet":
        fields_list.insert(0, ("q", { "help_text": "Filters according to a full-text search on the object.", "filterable": "Filterable (without operators)." }))
    
    return {
        "docstring": model.__doc__,
        "canonical_example": ex_id,
        "example_content": example_data,
        "fields_list": fields_list,
    }
    
