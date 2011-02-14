# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from person.models import Person

def person_redirect(request):
    pk = request.GET.get('id', None)
    person = get_object_or_404(Person, pk=pk)
    return redirect(person.get_absolute_url(), permanent=True)
