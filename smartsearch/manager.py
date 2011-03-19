"""
This is module automatically builds
search interface for the django model.
Search interface is a django form with extra features. The
main feature is the labels which displays the number of
possible results for each option.

`SearchManger` is the main objects which stores configuration.
`SearcManager` contains one or more `Option` objects.
`Option` object is reference to model field.
`SearchForm` is enchanced Django Form which associated with
`SearchManager` instance. `SearchForm` able to build itself
using options of SearchManager.

Example of usage:
    @render_to('someapp/user_list.html')
    def some_view(request):
        sm = SearchManager(User)
        sm.add_option('sex')
        # If we pass request to the `form` method
        # then the from will be bound with `request.GET` data
        form = sm.form(request)
        # Get the queryset limited
        # to selected options
        qs = form.queryset()
        return {'qs': qs, 'manager': sm}

Layout:
    Options <--> SearchManager <--> Form <--> (SmartSearchField or any other Field)
"""
from django import forms
from django.db.models import Count

class SearchManager(object):
    def __init__(self, model):
        self.model = model
        self.options = []
        self._form = None

    def add_option(self, *args, **kwargs):
        Option(self, *args, **kwargs)

    def form(self, request=None):
        if request:
            self._form = SearchForm(request.GET, manager=self)
        else:
            self._form = SearchForm(manager=self)
        return self._form


class Option(object):
    def __init__(self, manager, field_name, simple=False, field=None, required=False,
                 filter=None):
        """
        Args:
            manager: `SearchManager` instance
            field_name: name of model's field for which the filter shoudl be built
            simple: if True then use default model field's Form field
            field: if is not None then use that field in the form
            required: it will be passed later to field constructor
            filter: custom logic for filtering queryset
        """

        self.manager = manager
        self.field_name = field_name
        self.simple = simple
        self.field = field
        self.required = False
        self.filter = filter
        self.manager.options.append(self)


class SearchForm(forms.Form):
    manager = None
    def __init__(self, *args, **kwargs):
        self.manager = kwargs.pop('manager')
        for option in self.manager.options:
            if option.field:
                field = option.field
            elif option.simple:
                field = self.manager.model._meta.get_field(option.field_name).formfield()
            else:
                field = SmartChoiceField(self.manager.model, option.field_name, option.required)
            self.base_fields[option.field_name] = field
        super(SearchForm, self).__init__(*args, **kwargs)

    def queryset(self):
        qs = self.manager.model.objects.all()
        if self.is_valid():
            for option in self.manager.options:
                print 'Processing %s' % option.field_name
                if option.field_name in self.cleaned_data:
                    if option.filter is not None:
                        qs = option.filter(qs, self)
                    else:
                        values = self.cleaned_data[option.field_name]
                        if values:
                            if not u'__ALL__' in values:
                                qs = qs.filter(**{'%s__in' % option.field_name: values})
                print 'count', len(qs)
        return qs



class SmartChoiceField(forms.MultipleChoiceField):
    def __init__(self, model, field_name, required):
        # Do GROUP BY, then COUNT
        # http://docs.djangoproject.com/en/dev/topics/db/aggregation/#values
        resp = model.objects.values(field_name).annotate(_count=Count('id')).order_by()
        counts = dict((x[field_name], x['_count']) for x in resp)
        def generate_choices():
            yield ('__ALL__', 'All')
            for key, value in model._meta.get_field(field_name).choices:
                value += '(%d)' % counts.get(key, 0)
                yield (key, value)
        super(SmartChoiceField, self).__init__(
            required=required,
            choices=list(generate_choices()),
            widget=forms.CheckboxSelectMultiple)
