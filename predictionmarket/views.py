# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from common.decorators import render_to

from predictionmarket.models import TradingAccount

@login_required
@render_to('predictionmarket/account.html')
def accountinfo(request):
    user = request.user
    if user.is_superuser and "user" in request.GET: user = get_object_or_404(User, username=request.GET["user"])
    account = TradingAccount.get(user)
    return {
        'account': account,
        'trades': account.trades.order_by("-created").select_related(),
        }
 
