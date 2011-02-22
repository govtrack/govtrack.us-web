from committee.models import MEMBER_ROLE_WEIGHTS

def compare_members(a, b):
    """
    Commettee members should be displayed in sorted order.
    Comparison is performed with this function.
    """

    result = cmp(MEMBER_ROLE_WEIGHTS[a.role],
                 MEMBER_ROLE_WEIGHTS[b.role])
    if result != 0:
        return result
    else:
        return -1 * cmp(unicode(a.committee), unicode(b.committee))


def sort_members(members):
    """
    Commettee members should be displayed in sorted order.
    Sorting is performed with this function.
    """

    return sorted(members, cmp=compare_members, reverse=True)
