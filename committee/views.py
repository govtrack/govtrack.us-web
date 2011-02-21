# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from committee.models import Committee, CommitteeMemberRole
from committee.util import sort_members

@render_to('committee/committee_details.html')
def committee_details(request, parent_code, child_code=None):
    if child_code:
        obj = get_object_or_404(Committee, code=child_code, committee__code=parent_code)
        parent = obj.committee
    else:
        obj = get_object_or_404(Committee, code=parent_code)
        parent = None
    members = sort_members(obj.members.all())
    subcommittees = obj.subcommittees.all()
    return {'committee': obj,
            'parent': parent,
            'subcommittees': subcommittees,
            'members': members,
            'SIMPLE_MEMBER': CommitteeMemberRole.member,
            }

