# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse

from common.decorators import render_to
from common.pagination import paginate

from committee.models import Committee, CommitteeMemberRole, CommitteeType
from committee.util import sort_members

@render_to('committee/committee_details.html')
def committee_details(request, parent_code, child_code=None):
    from events.models import Feed
	
    if child_code:
        obj = get_object_or_404(Committee, code=child_code, committee__code=parent_code)
        parent = obj.committee
    else:
        obj = get_object_or_404(Committee, code=parent_code)
        parent = None
    members = sort_members(obj.members.all())
    subcommittees = obj.subcommittees.all()
    
    party_counts = { }
    for m in members:
        role = m.person.get_current_role()
        if role: # member left congress but is still listed as committee member
            party_counts[role.party] = party_counts.get(role.party, 0) + 1
    party_counts = sorted(party_counts.items(), key = lambda p : -p[1])
    
    return {'committee': obj,
            'parent': parent,
            'subcommittees': subcommittees,
            'members': members,
            'SIMPLE_MEMBER': CommitteeMemberRole.member,
            'TYPE_JOINT': CommitteeType.joint,
            'feed': Feed.CommitteeFeed(obj),
            "member_highlights": [m for m in members if m.role in (CommitteeMemberRole.chairman, CommitteeMemberRole.vice_chairman, CommitteeMemberRole.ranking_member)],
            "party_counts": party_counts,
            }

@render_to('committee/committee_list.html')
def committee_list(request):
    from events.models import Feed

    def key(x):
        return unicode(x).replace('the ', '')
    
    def getlist(type_):
        items = list(Committee.objects.filter(committee_type=type_, obsolete=False))
        return sorted(items, key=key)

    return {
        'senate_committees': getlist(CommitteeType.senate),
        'house_committees': getlist(CommitteeType.house),
        'joint_committees': getlist(CommitteeType.joint),
        'feed': Feed.AllCommitteesFeed(),
    }
