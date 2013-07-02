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
        if len(child_code) == 2:
            obj = get_object_or_404(Committee, code=parent_code+child_code)
        else: # legacy
            obj = get_object_or_404(Committee, code=child_code)
            return redirect(obj, permanent=True)
        parent = obj.committee
    else:
        obj = get_object_or_404(Committee, code=parent_code)
        parent = None
    members = sort_members(obj.members.all())
    subcommittees = sorted(obj.subcommittees.filter(obsolete=False), key=lambda s : s.name_no_article)
    
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
    import re

    def getlist(type_):
        items = list(Committee.objects.filter(committee_type=type_, obsolete=False))
        for c in items:
            m = re.match("(House|Senate) ((Select|Special|Permanent Select) )?Committee on (the )?(.+)", unicode(c))
            if not m:
                c.display_name = unicode(c)
            else:
                c.display_name = m.group(5)
        return sorted(items, key=lambda c : (not c.display_name.startswith("Joint "), c.display_name))

    return {
        'senate_committees': getlist(CommitteeType.senate),
        'house_committees': getlist(CommitteeType.house),
        'joint_committees': getlist(CommitteeType.joint),
        'feed': Feed.AllCommitteesFeed(),
    }
    
import django.contrib.sitemaps
class sitemap(django.contrib.sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 1.0
    def items(self):
        return Committee.objects.filter(obsolete=False)

