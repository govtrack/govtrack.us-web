# -*- coding: utf-8 -*-
from lxml.etree import fromstring

from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

@render_to('website/index.html')
def index(request):
    data = '<root><child><world>world!!</world></child></root>'
    world = fromstring(data).xpath('//world/text()')[0]
    return {'world': world,
            }
		  
@render_to('website/about.html')
def about(request):
    return {}
    
@render_to('website/district_map.html')
def browsemembers(request, state):
    from us import statelist, statenames, stateapportionment
    from person.models import Person
    from person.types import RoleType
    
    sens = None
    reps = None
    if state != None:
        if stateapportionment[state] != "T":
            sens = Person.objects.filter(roles__current=True, roles__state=state, roles__role_type=RoleType.senator)
            sens = list(sens)
            for i in xrange(2-len(sens)): # make sure we list at least two slots
                sens.append(None)
    
        reps = []
        if stateapportionment[state] in ("T", "1"):
            dists = [0]
        else:
            dists = xrange(1, stateapportionment[state]+1)
        for i in dists:
            try:
                reps.append((i, Person.objects.get(roles__current=True, roles__state=state, roles__role_type=RoleType.representative, roles__district=i)))
            except Person.DoesNotExist:
                reps.append((i, None))
    
    
    return {
        "state": state,
        "statename": statenames[state] if state != None else None,
        "statelist": statelist,
        "senators": sens,
        "reps": reps,
    }

