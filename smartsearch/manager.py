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

class SearchManager(object):
    def __init__(self, model, qs=None):
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

    def add_option(self, *args, **kwargs):
        Option(self, *args, **kwargs)
        
    def add_sort(self, sort_name, sort_key, default=False):
        self.sort_options.append( (sort_name, sort_key, default) )
        
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
                'sort_options': self.sort_options,
                'column_headers': self.get_column_headers(),
                'defaults': defaults,
                'noun_singular': noun[0],
                'noun_plural': noun[1],
                }
            c.update(context)
            return render_to_response(template, c, RequestContext(request))
        
        try:
            qs = self.queryset(request)
            
            if not paginate or paginate(request.POST):
                page_number = int(request.POST.get("page", "1"))
                per_page = 20
            else:
                page_number = 1
                per_page = len(qs)
            
            page = Paginator(qs, per_page)
            obj_list = page.page(page_number).object_list
            
            return HttpResponse(json.dumps({
                "results": self.results(obj_list, request.POST) if request.POST["faceting"]=="false" else None,
                "options": [(
                    option.field_name,
                    option.type,
                    self.generate_choices(request, option, omit_me=request.POST["faceting"]=="true"),
                    option.field_name in request.POST or option.field_name+"[]" in request.POST or option.visible_if(request.POST) if option.visible_if else True
                    ) for option in self.options],
                "page": page_number,
                "num_pages": page.num_pages,
                "per_page": per_page,
                "total_this_page": len(obj_list),
                "total": qs.count(),
                }), content_type='text/json')
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(json.dumps({
                "error": repr(e),
                }), content_type='text/json')
            
    def queryset(self, request, exclude=None):
        """
        Build the `self.model` queryset limited to selected filters.
        """

        if not self.qs:
            #qs = self.model.objects.all().select_related()
            from haystack.query import SearchQuerySet
            qs = SearchQuerySet().filter(indexed_model_name__in=[self.model.__name__])
        else:
            qs = self.qs

        filters = { }
        
        # Then for each filter
        for option in self.options:
            # If filter is not excluded explicitly (used to get counts
            # for choices).
            if option == exclude: continue
            
            # If filter contains valid data, check jQuery style encoding of array params
            if option.field_name not in request.POST and option.field_name+"[]" not in request.POST: continue
            
            # Do filtering

            if option.filter is not None:
                qs_ = option.filter(qs, request.POST)
                
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
                values = list(clean_values(request.POST.getlist(option.field_name)+request.POST.getlist(option.field_name+"[]")))
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
            if request.POST.get("sort", "") == key:
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
                        
    def generate_choices(self, request, option, omit_me=True):
        if option.type == "text":
            return None
        if option.type != "select":
            omit_me = True
        
        def get_value(f):
            if f in request.POST: return urllib.quote(request.POST[f])
            if f + "[]" in request.POST: return "&".join(urllib.quote(v) for v in sorted(request.POST.getlist(f + "[]")))
            return ""
        cache_key = "smartsearch_faceting_%s__%s__%s" % (
            self.model.__name__,
            option.field_name,
            "&".join( o.field_name + "=" + get_value(o.field_name) for o in self.options if (o.field_name in request.POST or o.field_name + "[]" in request.POST) and (not omit_me or o != option) ),
            )
        
        if option.choices:
            if callable(option.choices):
                counts = option.choices(request)
            else:
                counts = list(option.choices)
        else:
            ret = cache.get(cache_key)
            if ret: return ret
           
            # Get the model field metadata object that represents this field. 
            include_counts = True
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

            resp = self.queryset(request, exclude=option if omit_me else None)
            
            def build_choice(value, count):
                # (key, label, count, help_text) tuples
                return (value, nice_name(value, objs), count, getattr(field.choices.by_value(value), "search_help_text", None) if field and field.choices and type(field.choices) == MetaEnum else None)
            
            if hasattr(resp, 'facet'):
                # Haystack.
                resp = resp.facet(option.field_name).facet_counts()
                if len(resp) == 0:
                    return []
                facet_counts = resp["fields"][option.field_name]
                objs = get_object_set([opt[0] for opt in facet_counts])
                counts = [build_choice(opt[0], opt[1]) for opt in facet_counts               ]
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
            
        cache.set(cache_key, counts, 60*60) # cache facets for one hour

        return counts

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
        
