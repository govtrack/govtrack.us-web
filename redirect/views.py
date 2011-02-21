# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from person.models import Person
from committee.models import Committee

def person_redirect(request):
    pk = request.GET.get('id', None)
    person = get_object_or_404(Person, pk=pk)
    return redirect(person.get_absolute_url(), permanent=True)


def committee_redirect(request):
    pk = request.GET.get('id', None)
    if len(pk) > 4:
        parent_pk = pk[:4]
        child_pk = pk[4:]
        committee = get_object_or_404(Committee, code=child_pk, committee__code=parent_pk)
    else:
        committee = get_object_or_404(Committee, code=pk)
    return redirect(committee.get_absolute_url(), permanent=True)
