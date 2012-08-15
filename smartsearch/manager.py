"""
"""
from django import forms
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.db.models import Count
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.core.cache import cache

import json, urllib

from common.enum import MetaEnum

FACET_CACHE_TIME = 60*60

class SearchManager(object):
    def __init__(self, model, qs=None, connection=None):
        self.model = model
        self.qs = qs
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

    def add_option(self, *args, **kwargs):
        Option(self, *args, **kwargs)
        
    def add_sort(self, sort_name, sort_key, default=False):
        self.sort_options.append( (sort_name, sort_key, default) )
        
    def add_filter(self, key, value):
        self.global_filters[key] = value
        
    def add_left_column(self, title, func):
        self.col_left = func
        self.col_left_name = title
    def add_bottom_column(self, func):
        self.col_bottom = func
    def add_column(self, title, func):
        self.cols.append(func)
        self.colnames.append(title)

    def get_left_info(self, obj, form):
        if self.col_left == None:
            return ""
        else:
            return conditional_escape(self.col_left(obj, form))
        
    def get_column_headers(self):
        return [self.col_left_name] + self.colnames
        
    def get_columns(self, obj, form):
        if len(self.cols) == 0:
            cols = [unicode(obj)]
        else:
            cols = [c(obj, form) for c in self.cols]
        cols[0] = mark_safe(
            "<a href=\"" + conditional_escape(obj.get_absolute_url()) + "\">"
            + conditional_escape(cols[0])
            + "</a>"
            )
        
        return cols
        
    def get_bottom_info(self, obj, form):
        if self.col_bottom == None:
            return ""
        else:
            return mark_safe("".join(["<div>" + conditional_escape(line) + "</div>" for line in self.col_bottom(obj, form).split("\n")]))
        
    def make_result(self, obj, form):
        left = self.get_left_info(obj, form)
        cols = self.get_columns(obj, form)
        bottom = self.get_bottom_info(obj, form)
        
        return mark_safe(
            "<tr valign='top'>"
            + ("<td rowspan='2' class='rowtop rowleft'>%s</td>" % conditional_escape(left))
            + " ".join(
                [("<td class='rowtop col%d'>%s</td>" % (i, conditional_escape(col))) for i, col in enumerate(cols)]
                )
            + "</tr>"
            + ("<tr><td colspan='%d' style='vertical-align: top' class='rowbottom'>%s</td></tr>" % (len(cols), conditional_escape(bottom)))
            )
               
    def results(self, objects, form):
        return "".join([self.make_result(obj, form) for obj in objects])
        
    def view(self, request, template, defaults={}, noun=("item", "items"), context={}, paginate=None):
        if request.META["REQUEST_METHOD"] == "GET":
            c = {
                'form': self.options,
                'sort_options': [(name, key, isdefault if defaults.get("sort", None) == None else defaults.get("sort", None) == key) for name, key, isdefault in self.sort_options],
                'column_headers': self.get_column_headers(),
                'defaults': defaults,
                'noun_singular': noun[0],
                'noun_plural': noun[1],
                }
            c.update(context)
            return render_to_response(template, c, RequestContext(request))
        
        try:
            qs = self.queryset(request.POST)
            
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
                    if option.field_name in request.POST or option.field_name+"[]" in request.POST: continue
                    if option.type == "text": continue
                    if option.type == "select" and request.POST["faceting"]=="false": continue # 2nd phase only
                    loadable_facets.append(option.field_name)
                    faceted_qs = faceted_qs.facet(option.field_name)
                if len(loadable_facets) > 0:
                    cache_key = self.build_cache_key('bulkfaceting__' + ",".join(loadable_facets), request)
                    loaded_facets = cache.get(cache_key)
                    if not loaded_facets:
                        loaded_facets = faceted_qs.facet_counts()["fields"]
                        cache.set(cache_key, loaded_facets, FACET_CACHE_TIME)

            cache_key = self.build_cache_key('count', request)
            qs_count = cache.get(cache_key)
            if qs_count == None:
                qs_count = qs.count()
                cache.set(cache_key, qs_count, FACET_CACHE_TIME)
                
            def make_simple_choices(option):
                return option.type == "select" and not option.choices

            facets = [(
                option.field_name,
                option.type,
                
                self.generate_choices(request, option, loaded_facets,
                    # In order to speed up the display of results, we query the facet counts
                    # in two phases. The facet counts for select-type fields are delayed
                    # until the second phase (because you can't see them immediately).
                    # In the first phase, we cheat (to be quick) by not omitting the selected
                    # value in the facet counting query, which means we only get back the 
                    # counts for entries that match the currently selected value, which is
                    # all the user can see in the drop-down before the click the select box
                    # anyway. If the select field's value is unset (i.e. all), then we load
                    # all results in both phases.
                    simple=make_simple_choices(option) and request.POST["faceting"]=="false"),
                
                make_simple_choices(option) and request.POST["faceting"]=="false",
                
                option.field_name in request.POST or option.field_name+"[]" in request.POST or option.visible_if(request.POST) if option.visible_if else True
                ) for option in self.options
                    
                    # In the second phase, don't generate facets for options we've already
                    # done in the first phase.
                    if request.POST["faceting"]=="false" or make_simple_choices(option)
                ]

            if request.POST["faceting"] == "false":
                if not paginate or paginate(request.POST):
                    page_number = int(request.POST.get("page", "1"))
                    per_page = 20
                else:
                    page_number = 1
                    per_page = qs_count
                
                page = Paginator(qs, per_page)
                obj_list = page.page(page_number).object_list
            
                ret = {
                    "results": self.results(obj_list, request.POST),
                    "options": facets,
                    "page": page_number,
                    "num_pages": page.num_pages,
                    "per_page": per_page,
                    "total_this_page": len(obj_list),
                    "total": qs_count,
                }
                
                try:
                    ret["description"] = self.describe(dict(request.POST.iterlists()))
                except:
                    pass # self.describe is untested

            else:
                ret = facets

            return HttpResponse(json.dumps(ret), content_type='text/json')
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
        
        if not self.qs:
            #qs = self.model.objects.all().select_related()
            from haystack.query import SearchQuerySet
            qs = SearchQuerySet()
            if self.connection: qs = qs.using(self.connection)
            qs = qs.filter(indexed_model_name__in=[self.model.__name__], **self.global_filters)
        else:
            qs = self.qs

        filters = { }
        
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
                def clean_values(x):
                    for y in x:
                        if y in ("true", "on"):
                            yield True
                        elif y == "false":
                            yield False
                        else:                        
                            yield y
                values = list(clean_values(postdata.getlist(option.field_name)+postdata.getlist(option.field_name+"[]")))
                # if __ALL__ value presents in filter values
                # then do not limit queryset
                if not u'__ALL__' in values:
                    filters.update({'%s__in' % option.field_name: values})

        # apply filters simultaneously so that filters on related objects are applied
        # to the same related object. if they were applied chained (i.e. filter().filter())
        # then they could apply to different objects.
        if len(filters) > 0:
            qs = qs.filter(**filters)
            
        for name, key, default in self.sort_options:
            if postdata.get("sort", "") == key:
                qs = qs.order_by(key)
        
        # Django ORM but not Haystack
        if hasattr(qs, 'distinct'):
            return qs.distinct()
            
        # Haystack but not Django ORM
        else:
            # Revise the SearchQuerySet to iterate over model objects
            # rather than SearchResult objects.
            class SR:
                def __init__(self, qs):
                    self.qs = qs
                def facet(self, field):
                    return self.qs.facet(field)
                def count(self):
                    return len(self.qs)
                def __len__(self):
                    return len(self.qs)
                def __getitem__(self, index):
                    return SR(self.qs[index])
                def __iter__(self):
                    for item in self.qs:
                        yield item.object
            return SR(qs)
            
    def build_cache_key(self, prefix, request, omit=None):
        def get_value(f):
            if f in request.POST: return urllib.quote(request.POST[f])
            if f + "[]" in request.POST: return "&".join(urllib.quote(v) for v in sorted(request.POST.getlist(f + "[]")))
            return ""
        return "smartsearch_%s_%s__%s" % (
            self.model.__name__,
            prefix,
            "&".join( unicode(k) + "=" + unicode(v) for k, v in self.global_filters.items() )
            + "&&" +
            "&".join( o.field_name + "=" + get_value(o.field_name) for o in self.options if (o.field_name in request.POST or o.field_name + "[]" in request.POST) and (o != omit) ),
            )        
                        
    def get_model_field(self, option):
        include_counts = True
        choice_label_map = None
        try:
            meta = self.model._meta
            if "__" not in option.field_name:
                fieldname = option.field_name
            else:
                include_counts = False # one-to-many relationships make the aggregation return non-distinct results
                path = option.field_name.split("__")
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
                        
    def generate_choices(self, request, option, loaded_facets, simple=False):
        # There are no facets for text-type fields.
        if option.type == "text":
            return None
            
        # Option is not set and we only want simple results.
        if simple and not (option.field_name in request.POST or option.field_name+"[]" in request.POST or option.field_name in self.global_filters):
            return [('__ALL__', 'All', -1, None)]

        cache_key = self.build_cache_key('faceting__' + option.field_name, request, omit=option if not simple else None)
        
        if option.choices:
            if callable(option.choices):
                counts = option.choices(request)
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
                    # values+annotate makes the db return an integer rather than an object
                    return field.rel.to.objects.in_bulk(ids)
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
                        return unicode(objs[value])
                    value = field.rel.to.objects.get(id=value)
                return unicode(value)

            def build_choice(value, count):
                # (key, label, count, help_text) tuples
                return (value, nice_name(value, objs), count, getattr(field.choices.by_value(value), "search_help_text", None) if field and field.choices and type(field.choices) == MetaEnum else None)
            
            if loaded_facets and option.field_name in loaded_facets:
                # Facet counts were already loaded.
                facet_counts = loaded_facets[option.field_name]
                objs = get_object_set([opt[0] for opt in facet_counts])
                counts = [build_choice(opt[0], opt[1]) for opt in facet_counts]
            else:
                resp = self.queryset(request.POST, exclude=option if not simple else None)
                
                if hasattr(resp, 'facet'):
                    # Haystack.
                    resp = resp.facet(option.field_name).facet_counts()
                    if len(resp) == 0:
                        return []
                    facet_counts = resp["fields"][option.field_name]
                    objs = get_object_set([opt[0] for opt in facet_counts])
                    counts = [build_choice(opt[0], opt[1]) for opt in facet_counts]
                else:
                    # ORM explanation: do GROUP BY, then COUNT
                    # http://docs.djangoproject.com/en/dev/topics/db/aggregation/#values
                    resp = resp\
                               .values(option.field_name)\
                               .annotate(_count=Count('id'))\
                               .distinct().order_by()
                           
                    objs = get_object_set([x[option.field_name] for x in resp if x[option.field_name] != ""])
                    counts = [ 
                        build_choice(x[option.field_name], x['_count'] if include_counts else None)
                        for x in resp if x[option.field_name] != ""]
            
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
        
    def execute_qs(self, qs, defaults=None, overrides=None):
        from django.http import QueryDict
        qd = QueryDict(qs).copy() # copy makes mutable
        if defaults:
            for k in defaults:
                qd.setdefault(k, defaults[k])
        if overrides:
            for k in overrides:
                qd[k] = overrides[k]
        return self.queryset(qd)

    def describe_qs(self, qs):
        import urlparse
        return self.describe(urlparse.parse_qs(qs))
        
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
                        value = field.rel.to.objects.get(id=v)
                    if option.formatter: return option.formatter(value)
                    return unicode(value)
                
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
                 visible_if=None, help=None, formatter=None):
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
        
