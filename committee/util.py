from committee.models import MEMBER_ROLE_WEIGHTS

def sort_members(members):
    """
    Commettee members should be displayed in sorted order.
    Sorting is performed with this function.
    """

    def role_w(r):
        if r is None: return -1
        return MEMBER_ROLE_WEIGHTS[r.role]
    return sorted(members, key=lambda c : (-MEMBER_ROLE_WEIGHTS[c.role], -role_w(c.subcommittee_role()), c.person.name_no_details_lastfirst(), c.committee.shortname))
