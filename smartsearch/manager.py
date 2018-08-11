"""
"""
from django import forms
from django.shortcuts import redirect, get_object_or_404, render
from django.template import Template, Context
from django.template.loader import get_template
from django.db.models import Count
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.core.cache import cache

import json, urllib.request, urllib.parse, urllib.error, hashlib

from common.enum import MetaEnum
import collections

FACET_CACHE_TIME = 60*60
FACET_OPTIONS = { "limit": -1, "mincount": 1, "sort": "count" } # limits cause problems because the selected option can dissapear!

class SearchManager(object):
    def __init__(self, model, qs=None, connection=None, bulk_loader=None):
        self.model = model
        self.qs = qs
        self.bulk_loader = (bulk_loader or model.objects.in_bulk)
        self.options = []
        self._form = None
        self.col_left = None
        self.col_left_name = None
        self.col_bottom = None
        self.cols = []
        self.colnames = []
        self.sort_options = []
        self.global_filters = { }
        self.connection = connection
        self.template = None
        self.template_context_func = None

    def add_option(self, *args, **kwargs):
        Option(self, *args, **kwargs)
        
    def add_sort(self, sort_name, sort_key, default=False, func=None):
        self.sort_options.append( (sort_name, sort_key, default, func) )
        
    def add_filter(self, key, value):
        self.global_filters[key] = value
        
    def set_template(self, template_data):
        self.template = Template(template_data)
    def set_template_file(self, template_file_name):
        self.template = get_template(template_file_name)
    def set_template_context_func(self, func):
        self.template_context_func = func
        
    def results(self, objects, form):
        if not self.template:
            self.template = get_template("smartsearch/search-result-item.html")
        if not self.template_context_func:
            self.template_context_func = lambda obj, form : Context({ "object": obj, "form": form })
        return [self.template.render(self.template_context_func(obj, form)) for obj in objects]
    
    def view(self, request, template, defaults={}, noun=("item", "items"), context={}, paginate=None):
        if request.META["REQUEST_METHOD"] == "GET" \
        	and request.GET.get('do_search', None) == None:
            c = {
                'form': self.options,
                'has_relevance_sort': self.qs is None,
                'sort_options': [(name, key, isdefault if defaults.get("sort", None) == None else defaults.get("sort", None) == key) for name, key, isdefault, func in self.sort_options],
                'defaults': defaults,
                'noun_singular': noun[0],
                'noun_plural': noun[1],
                }
            c.update(context)
            return render(request, template, c)
            
        # Get the dict of params. We use .urlencode() on the dict which is available for .GET and .POST
        # but not .REQUEST. We can switch completely to request.GET later, after a transition time
        # which caches expire.
        qsparams = (request.GET if request.META["REQUEST_METHOD"] == "GET" else request.POST)

        # Although we cache some facet queries, also cache the final response.
        m = hashlib.md5()
        m.update((self.model.__name__ + "|" + qsparams.urlencode()).encode("utf8"))
        cachekey = "smartsearch__response__" + m.hexdigest()
        resp = cache.get(cachekey)
        if resp and False:
            resp = HttpResponse(resp, content_type='text/json')
            resp["X-Cached"] = "True"
            return resp

        try:
            qs = self.queryset(qsparams)
            
            # In order to generate the facets, we will call generate_choices on each
            # visible search field. When generating facets with the Django ORM, a
            # separate query is required because only one .annotate() can be used
            # at a time. However, with Haystack we can facet on multiple fields at
            # once efficiently.
            #
            # Still, the underlying queries are different for fields that have values
            # chosen by the user. Each facet shows the counts of matched objects
            # by value, including the filtering set on other fields, but of course not
            # the filtering set on its own field because then it would return just
            # one category.
            #
            # So optimizing the facet query for Haystack can pre-load only the facets
            # that have the same underlying query --- i.e. only the facets that have
            # no value set by the user.
            loaded_facets = None
            if hasattr(qs, 'facet'):
                faceted_qs = qs
                loadable_facets = []
                for option in self.options:
                    if option.filter: continue
                    if option.field_name in qsparams or option.field_name+"[]" in qsparams: continue
                    if option.type == "text": continue
                    if option.type == "select" and qsparams["faceting"]=="false": continue # 2nd phase only
                    loadable_facets.append(option.field_name)
                    faceted_qs = faceted_qs.facet(option.orm_field_name, **FACET_OPTIONS)
                if len(loadable_facets) > 0:
                    cache_key = self.build_cache_key('bulkfaceting__' + ",".join(loadable_facets), qsparams)
                    loaded_facets = cache.get(cache_key)
                    if not loaded_facets:
                        fq = faceted_qs.facet_counts()
                        if "fields" in fq: # don't know why it sometimes gives nothing
                            loaded_facets = fq["fields"]
                            for k, v in list(loaded_facets.items()):
                                loaded_facets[k] = self.filter_facet_counts(k, v)
                            cache.set(cache_key, loaded_facets, FACET_CACHE_TIME)

            # At the moment there's no need to cache the count because we also cache the final response.
            #cache_key = self.build_cache_key('count', qsparams)
            #qs_count = cache.get(cache_key)
            #if qs_count == None:
            #    qs_count = qs.count()
            #    cache.set(cache_key, qs_count, FACET_CACHE_TIME)
            qs_count = qs.count()
                
            def make_simple_choices(option):
                return option.type == "select" and not option.choices

            facets = [(
                option.field_name,
                option.type,
                
                self.generate_choices(qsparams, option, loaded_facets,
                    # In order to speed up the display of results, we query the facet counts
                    # in two phases. The facet counts for select-type fields are delayed
                    # until the second phase (because you can't see them immediately).
                    # In the first phase, we cheat (to be quick) by not omitting the selected
                    # value in the facet counting query, which means we only get back the 
                    # counts for entries that match the currently selected value, which is
                    # all the user can see in the drop-down before the click the select box
                    # anyway. If the select field's value is unset (i.e. all), then we load
                    # all results in both phases.
                    simple=make_simple_choices(option) and qsparams["faceting"]=="false"),
                
                make_simple_choices(option) and qsparams["faceting"]=="false",
                
                option.field_name in qsparams or option.field_name+"[]" in qsparams or option.visible_if(qsparams) if option.visible_if else True
                ) for option in self.options
                    
                    # In the second phase, don't generate facets for options we've already
                    # done in the first phase.
                    if qsparams["faceting"]=="false" or make_simple_choices(option)
                ]

            if qsparams["faceting"] == "false":
                if not paginate or paginate(qsparams):
                    page_number = int(qsparams.get("page", "1"))
                    per_page = 20
                else:
                    page_number = 1
                    per_page = qs_count
                
                page = Paginator(qs, per_page)
                obj_list = page.page(page_number).object_list if qs_count > 0 else []
            
                ret = {
                    "results": self.results(obj_list, qsparams),
                    "options": facets,
                    "page": page_number,
                    "num_pages": page.num_pages if qs_count > 0 else 0,
                    "per_page": per_page,
                    "total_this_page": len(obj_list),
                    "total": qs_count,
                }
                
                try:
                    ret["description"] = self.describe(dict(qsparams.iterlists()))
                except:
                    pass # self.describe is untested

            else:
                ret = facets

            #from django.db import connection
            #ret['queries'] = connection.queries

            # Cache the final response for 5 minutes.
            ret = json.dumps(ret)
            #cache.set(cachekey, ret, 60*5) # TOO BIG TO CACHE
            return HttpResponse(ret, content_type='text/json')
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({
                "error": repr(e),
                "stack": traceback.format_exc().split("\n"),
                }), content_type='text/json')
            
    def queryset(self, postdata, exclude=None):
        """
        Build the `self.model` queryset limited to selected filters.
        """

        from haystack.query import SearchQuerySet
        
        if self.qs is None:
            #qs = self.model.objects.all().select_related()
            qs = SearchQuerySet()
            if self.connection: qs = qs.using(self.connection)
            qs = qs.filter(indexed_model_name__in=[self.model.__name__], **self.global_filters)
        else:
            qs = self.qs

        filters = { }
        filters2 = []
        
        # Then for each filter
        for option in self.options:
            # If filter is not excluded explicitly (used to get counts
            # for choices).
            if option == exclude: continue
            
            # If filter contains valid data, check jQuery style encoding of array params
            if option.field_name not in postdata and option.field_name+"[]" not in postdata: continue
            
            # Do filtering

            if option.filter is not None:
                qs_ = option.filter(qs, postdata)
                
                if isinstance(qs_, dict):
                    filters.update(qs_)
                else:
                    qs = qs_
                
            else:
                values = postdata.getlist(option.field_name)+postdata.getlist(option.field_name+"[]")
                
                if option.type == "text":
                    # For full-text searching, don't use __in so that the search
                    # backend does its usual query operation.
                    values = " ".join(values) # should not really be more than one, but in case the parameter is specified multiple times in the query string
                    if self.qs is None:
                       # This is a Haystack search. Handle text a little differently.
                       # Wrap it in an AutoQuery so advanced search options like quoted phrases are used.
                       # Query both text and text_boosted, which has a boost applied at the field level.
                       from haystack.query import SQ
                       from haystack.inputs import AutoQuery
                       values = AutoQuery(values)
                       filters2.append( SQ(text=values) | SQ(text_boosted=values) )
                    else:
                       filters[option.orm_field_name] = values
                    
                elif not '__ALL__' in values:
                    # if __ALL__ value presents in filter values
                    # then do not limit queryset

                    def parse_booleans(x):
                        for y in x:
                            if y in ("true", "on"):
                                yield True
                            elif y == "false":
                                yield False
                            else:                        
                                yield y
                    values = list(parse_booleans(values))

                    filters['%s__in' % option.orm_field_name] = values

        # apply filters simultaneously so that filters on related objects are applied
        # to the same related object. if they were applied chained (i.e. filter().filter())
        # then they could apply to different objects.
        if len(filters) + len(filters2) > 0:
            qs = qs.filter(*filters2, **filters)
            
        for name, key, default, func in self.sort_options:
            if postdata.get("sort", "") == key:
                if not func:
                    qs = qs.order_by(key)
                else:
                    qs = func(qs)
        
        # Django ORM but not Haystack
        if hasattr(qs, 'distinct'):
            return qs.distinct()
            
        # Haystack but not Django ORM
        elif isinstance(qs, SearchQuerySet):
            # Revise the SearchQuerySet to iterate over model objects
            # rather than SearchResult objects.
            class SR:
                def __init__(self, qs, manager):
                    self.qs = qs
                    self.manager = manager
                def facet(self, field, **kwargs):
                    return self.qs.facet(field, **kwargs)
                def count(self):
                    return len(self.qs)
                def order_by(self, field):
                    return SR(self.qs.order_by(field), self.manager)
                def __len__(self):
                    return len(self.qs)
                def __getitem__(self, index): # slices too, yields a list?
                    return SR(self.qs[index], self.manager)
                def __iter__(self):
                    # Pre-load all objects in bulk. Then yield in the right order.
                    objects = self.manager.bulk_loader(item.pk for item in self.qs)
                    for item in self.qs:
                        yield objects[int(item.pk)]
            return SR(qs, self)

        else:
            raise ValueError(qs)
            
    def build_cache_key(self, prefix, qsparams, omit=None):
        import hashlib
        hasher = hashlib.sha1
        def get_value(f):
            if f in qsparams: return urllib.parse.quote(qsparams[f])
            if f + "[]" in qsparams: return "&".join(urllib.parse.quote(v) for v in sorted(qsparams.getlist(f + "[]")))
            return ""
        return "smartsearch_%s_%s__%s" % (
            self.model.__name__,
            prefix,
            hasher((
                "&".join( str(k) + "=" + str(v) for k, v in list(self.global_filters.items()) )
                + "&&" +
                "&".join( o.field_name + "=" + get_value(o.field_name) for o in self.options if (o.field_name in qsparams or o.field_name + "[]" in qsparams) and (o != omit) )
            ).encode("utf8")).hexdigest()
            )
                        
    def get_model_field(self, option):
        include_counts = True
        choice_label_map = None
        try:
            meta = self.model._meta
            if "__" not in option.orm_field_name:
                fieldname = option.orm_field_name
            else:
                include_counts = False # one-to-many relationships make the aggregation return non-distinct results
                path = option.orm_field_name.split("__")
                fieldname = path.pop()
                for p in path:
                    meta = [f.model._meta for f in meta.get_all_related_objects() if f.get_accessor_name() == p][0]
            field = meta.get_field(fieldname)
            if field.choices:
                choice_label_map = dict(field.choices)
        except:
            # Some fields indexed by Haystack may not be model fields.
            field = None
        return include_counts, field, choice_label_map
                        
    def generate_choices(self, qsparams, option, loaded_facets, simple=False):
        # There are no facets for text-type fields.
        if option.type == "text":
            return None
            
        # Option is not set and we only want simple results.
        if simple and not (option.field_name in qsparams or option.field_name+"[]" in qsparams or option.field_name in self.global_filters):
            return [('__ALL__', 'All', -1, None)]

        cache_key = self.build_cache_key('faceting__' + option.field_name, qsparams, omit=option if not simple else None)
        
        if option.choices:
            if callable(option.choices):
                counts = option.choices(qsparams)
            else:
                counts = list(option.choices)
        else:
            ret = cache.get(cache_key)
            if ret: return ret
           
            # Get the model field metadata object that represents this field. 
            include_counts, field, choice_label_map = self.get_model_field(option)
            
            # Calculate number of possible results for each option, using the current
            # search terms except for this one.
            # Use `form.queryset()` to track already applied options
            
            def get_object_set(ids):
                if not field: return None
                if field.choices: return None
                if field.__class__.__name__ in ('ForeignKey', 'ManyToManyField'):
                    # values+annotate makes the db return an integer rather than an object,
                    # and Haystack always returns integers rather than objects
                    return field.related_model.objects.in_bulk(ids)
                return None

            def nice_name(value, objs):
                if value == None: return "N/A"
                if option.formatter: return option.formatter(objs[value] if objs and value in objs else value)
                if field and field.choices and value in choice_label_map:
                    return choice_label_map[value]
                if type(value) == bool and value == True: return "Yes"
                if type(value) == bool and value == False: return "No"
                if field and field.__class__.__name__ in ('ForeignKey', 'ManyToManyField'):
                    # values+annotate makes the db return an integer rather than an object
                    if objs and value in objs:
                        return str(objs[value])
                    value = field.related_model.objects.get(id=value)
                return str(value)
            
            def fix_value_type(value):
                # Solr and ElasticSearch return strings on integer data types.
                if isinstance(value, str) and field.__class__.__name__ in ('IntegerField', 'ForeignKey', 'ManyToManyField'):
                    return int(value)
                return value

            def build_choice(value, count):
                # (key, label, count, help_text) tuples
                value = fix_value_type(value)
                return (
                    value,
                    nice_name(value, objs),
                    count,
                    getattr(field.choices.by_value(value), "search_help_text", None)
                        if field and field.choices and type(field.choices) == MetaEnum else None)
            
            if loaded_facets and option.field_name in loaded_facets:
                # Facet counts were already loaded.
                facet_counts = loaded_facets[option.field_name]
                objs = get_object_set([opt[0] for opt in facet_counts])
                counts = [build_choice(opt[0], opt[1]) for opt in facet_counts]
            else:
                resp = self.queryset(qsparams, exclude=option if not simple else None)
                
                if hasattr(resp, 'facet'):
                    # Haystack.
                    resp = resp.facet(option.orm_field_name, **FACET_OPTIONS).facet_counts()
                    if len(resp) == 0:
                        return []
                    facet_counts = resp["fields"][option.orm_field_name]
                    facet_counts = self.filter_facet_counts(option.orm_field_name, facet_counts)
                    objs = get_object_set([opt[0] for opt in facet_counts])
                    counts = [build_choice(opt[0], opt[1]) for opt in facet_counts]
                else:
                    # ORM explanation: do GROUP BY, then COUNT
                    # http://docs.djangoproject.com/en/dev/topics/db/aggregation/#values
                    resp = resp\
                               .values(option.orm_field_name)\
                               .annotate(_count=Count('id'))\
                               .distinct().order_by()
                           
                    objs = get_object_set([x[option.orm_field_name] for x in resp if x[option.orm_field_name] != ""])
                    counts = [ 
                        build_choice(x[option.orm_field_name], x['_count'] if include_counts else None)
                        for x in resp if x[option.orm_field_name] != ""]
                        
            ## Stock Solr returns facets that have 0 count. Filter those out.
            ## Except we're using my fork to unset the facet limit.
            #counts = [c for c in counts if c[2] > 0]
            
            # Sort by count then by label.
            if option.sort == "COUNT":
                counts.sort(key=lambda x: (-x[2] if x[2] != None else None, x[1]))
            elif option.sort == "KEY":
                counts.sort(key=lambda x: x[0])
            elif option.sort == "KEY-REVERSE":
                counts.sort(key=lambda x: x[0], reverse=True)
            elif option.sort == "LABEL":
                counts.sort(key=lambda x: x[1])
            elif option.sort == "LABEL-REVERSE":
                counts.sort(key=lambda x: x[1], reverse=True)
            elif callable(option.sort):
                counts.sort(key=lambda x : option.sort( objs[x[0]] if objs and x[0] in objs else x[0] ))

        if not option.required and counts != "NONE":
            counts.insert(0, ('__ALL__', 'All', -1, None))
            
        cache.set(cache_key, counts, FACET_CACHE_TIME)

        return counts
        
    def filter_facet_counts(self, fieldname, counts):
        # Don't show facets that should be filtered out. Solr facets always come back as strings,
        # so stringify too.
        def should_show_count(key, count):
            if fieldname in self.global_filters:
                return key in (self.global_filters[fieldname], str(self.global_filters[fieldname]))
            if fieldname + "__in" in self.global_filters:
                return key in list(self.global_filters[fieldname+ "__in"]) + list(str(s) for s in self.global_filters[fieldname+ "__in"])
            return True
        return [kv for kv in counts if should_show_count(kv[0], kv[1])]

    def execute_qs(self, qs, defaults=None, overrides=None):
        from django.http import QueryDict
        qd = QueryDict(qs.encode("utf8")).copy() # QueryDict() expects a binary string, copy makes mutable
        if defaults:
            for k in defaults:
                qd.setdefault(k, defaults[k])
        if overrides:
            for k in overrides:
                qd[k] = overrides[k]
        return self.queryset(qd)

    def describe_qs(self, qs):
        import urllib.parse
        return self.describe(urllib.parse.parse_qs(qs))
        
    def describe(self, qs): # qs is a dict from field names to a list of values, like request.POST
        descr = []
        for option in self.options:
            if option.field_name not in qs: continue
            
            # Get a function to format the value.
            include_counts, field, choice_label_map = self.get_model_field(option)
            if option.type == "text":
                # Pass through text fields.
                formatter = lambda v : v
            elif option.choices or choice_label_map:
                # If choices are specified on the option or on the ORM field, use that.
                choices = choice_label_map
                if option.choices: choices = option.choices
                choices = dict((str(k), v) for k,v in choices) # make sure keys are strings
                formatter = lambda v : choices[v]
            else:
                def formatter(value):
                    # If the ORM field is for objects, map ID to an object value, then apply option formatter. 
                    if field and field.__class__.__name__ in ('ForeignKey', 'ManyToManyField'):
                        value = field.related_model.objects.get(id=v)
                    if option.formatter: return option.formatter(value)
                    return str(value)
                
            vals = []
            for v in qs[option.field_name]:
                vals.append(formatter(v))
            
            if option.type == "text":
                descr.append(", ".join(vals))
            else:
                label = option.label
                if not label: label = option.field_name
                descr.append(label + ": " + ", ".join(vals))
        
        return "; ".join(descr)

class Option(object):
    def __init__(self, manager, field_name, type="checkbox", required=False,
                 filter=None, choices=None, label=None, sort="COUNT",
                 visible_if=None, help=None, formatter=None, orm_field_name=None):
        """
        Args:
            manager: `SearchManager` instance
            field_name: name of model's field for which the filter shoudl be built
            type: text, select, or checkbox
            required: set to True to not include the ALL option
            filter: custom logic for filtering queryset
            choices: override the choices available
            label: override the label
            visible_if: show this option only if a function returns true (passed one arg, the request.POST)
        """

        self.manager = manager
        self.field_name = field_name
        self.type = type
        self.required = required
        self.filter = filter
        self.manager.options.append(self)
        self.choices = choices
        self.label = label
        self.sort = sort
        self.visible_if = visible_if
        self.help = help
        self.formatter = formatter
        self.orm_field_name = orm_field_name if orm_field_name else field_name
        
