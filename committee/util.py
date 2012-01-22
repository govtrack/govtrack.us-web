from committee.models import MEMBER_ROLE_WEIGHTS

def sort_members(members):
    """
    Commettee members should be displayed in sorted order.
    Sorting is performed with this function.
    """

    return sorted(members, key=lambda c : (-MEMBER_ROLE_WEIGHTS[c.role], not c.subcommittee_role(), c.person.name_no_details_lastfirst()))
