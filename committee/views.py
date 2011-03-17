# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from committee.models import Committee, CommitteeMemberRole, CommitteeType
from committee.util import sort_members

@render_to('committee/committee_details.html')
def committee_details(request, parent_code, child_code=None):
    from events.feeds import CommitteeFeed
	
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
            'feed': CommitteeFeed(obj.code),
            }

@render_to('committee/committee_list.html')
def committee_list(request):
    from events.feeds import AllCommitteesFeed

    def key(x):
        return unicode(x).replace('the ', '')
    
    def getlist(type_):
        items = list(Committee.objects.filter(committee_type=type_, obsolete=False))
        return sorted(items, key=key)

    return {
        'senate_committees': getlist(CommitteeType.senate),
        'house_committees': getlist(CommitteeType.house),
        'joint_committees': getlist(CommitteeType.joint),
        'feed': AllCommitteesFeed(),
    }
