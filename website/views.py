# -*- coding: utf-8 -*-
from lxml.etree import fromstring

from django.http import Http404
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

@render_to('website/index.html')
def index(request):
    data = '<root><child><world>world!!</world></child></root>'
    world = fromstring(data).xpath('//world/text()')[0]
    return {'world': world,
            }
		  
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    return render_to_response('website/' + pagename + '.html', { }, RequestContext(request))

@render_to('website/congress_home.html')
def congress_home(request):
    return {}
