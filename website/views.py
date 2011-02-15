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
