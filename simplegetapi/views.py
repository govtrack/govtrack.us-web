from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, Http404
from django.db.models import Model
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.related import RelatedObject
from django.shortcuts import get_object_or_404
from django.conf import settings
from common import enum as enummodule
import csv, json, StringIO, datetime, lxml

def is_enum(obj):
    import inspect
    return inspect.isclass(obj) and issubclass(obj, enummodule.Enum)

def serialize(obj, recurse_on=[], requested_fields=None):
    if isinstance(obj, (str, unicode, int, long, float, list, tuple, dict)) or obj is None:
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
        for field in obj._meta.fields + obj._meta.many_to_many + obj._meta.get_all_related_objects() + list(getattr(obj, "api_additional_fields", {})):
            # Get the field name.
            if isinstance(field, (str, unicode)): # for api_additional_fields
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
            if not isinstance(field, (str, unicode)):
                try:
                    v = getattr(obj, field_name)
                except:
                    v = None
            else:
                # for api_additional_fields
                v = obj.api_additional_fields[field]
                if not callable(v):
                    v = getattr(obj, v)
                    if callable(v):
                        v = v()
                else:
                    v = v(obj)
            
            # When serializing inside objects, if we have a field_name__subfield
            # entry in recurse_on, pass subfield to the inside serialization.
            sub_recurse_on = [r[len(field_name)+2:] for r in recurse_on if r.startswith(field_name + "__")]

            # Likewise for user-pulled fields.
            sub_fields = [r[len(field_name)+2:] for r in requested_fields if r.startswith(field_name + "__")] if requested_fields is not None else None

            if isinstance(field, ManyToManyField) or str(type(v)) == "<class 'django.db.models.fields.related.RelatedManager'>":
                if field_name in recurse_on:
                    ret[field_name] = [serialize(vv, recurse_on=sub_recurse_on, requested_fields=sub_fields) for vv in v.all()]
                #elif with_simple_m2ms:
                #    ret[field_name] = list(int(x) for x in v.all().values_list('id', flat=True))
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
            # Allow filtering on all Django ORM fields with db_index=True
            # by default, unless api_allowed_filters is specified. Don't
            # allow large offsets because the MySQL query optimizer fails
            # badly.
            default_filterable_fields = [f.name for f in model._meta.fields if f.name == 'id' or f.db_index]
            fields = set(getattr(model, "api_allowed_filters", default_filterable_fields))
            def is_filterable_field(f): return f in fields
            is_sortable_field = is_filterable_field
            allow_large_offset = False
        else:
            # Allow filtering on fields indexed in Haystack.
            fields = set(getattr(model, "haystack_index", [])) | set(f[0] for f in getattr(model, "haystack_index_extra", []))
            def is_filterable_field(f): return f in fields
            def is_sortable_field(f): return f in fields
            allow_large_offset = True
        
        for arg, vals in request.GET.iterlists():
            if arg in ("offset", "limit", "format", "fields"):
                pass
            
            elif arg in ("sort", "order_by"):
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
                
                if len(arg_parts) == 2 and arg_parts[1] not in ("contains", "exact", "gt", "gte", "lt", "lte", "in", "startswith", "range"):
                    # e.g. field1__field2 => ('field1__field12', 'exact')
                    arg_parts[0] += "__" + arg_parts[1]
                    arg_parts.pop()
                    
                if len(arg_parts) == 1: arg_parts.append("exact") # default operator
                fieldname, matchoperator = arg_parts
                
                if not is_filterable_field(fieldname):
                    return HttpResponseBadRequest("Invalid field name for filter: %s" % fieldname)
                    
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
                except Exception as e:
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
            
        if offset > 10000 and not allow_large_offset:
            return HttpResponseBadRequest("Offset > 10000 is not supported for this data type. Try a __gt filter instead.")
            
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
        ret = json.dumps(response, sort_keys=True, ensure_ascii=False, indent=True)
        resp = HttpResponse(ret, mimetype="application/json")
        resp["Content-Length"] = len(ret)
        return resp
        
    elif format == "xml":
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
        if len(raw_data) > 500000:
            resp['Content-Disposition'] = 'attachment; filename="query.csv"'
        else:
            resp['Content-Disposition'] = 'inline; filename="query.csv"'
        return resp
        
    else:
        return HttpResponseBadRequest("Invalid response format: %s." % format)
        
