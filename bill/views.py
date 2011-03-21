# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate
