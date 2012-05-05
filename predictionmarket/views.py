# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.contrib.auth.decorators import login_required

from common.decorators import render_to

from predictionmarket.models import TradingAccount

@login_required
@render_to('predictionmarket/account.html')
def accountinfo(request):
    account = TradingAccount.get(request.user)
    return {
        'account': account,
        'trades': account.trades.order_by("-created").select_related(),
        }
 
