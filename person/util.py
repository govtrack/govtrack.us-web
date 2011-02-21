from committee.models import CommitteeMemberRole

def get_committee_assignments(person):
    """
    Find committee assignments for the given person
    in current congress.

    Returns sorted list of CommitteeMemberRole objects where each object is
    committee assinment which could has subcommittee assignments in ``subroles`` attribute.
    """

    role_weights = {
        CommitteeMemberRole.chairman: 5,
        CommitteeMemberRole.vice_chairman: 4,
        CommitteeMemberRole.ranking_member: 3,
        CommitteeMemberRole.exofficio: 2,
        CommitteeMemberRole.member: 1
    }
    def cmp_roles(a, b):
        result = cmp(role_weights[a.role], role_weights[b.role])
        if result != 0:
            return result
        else:
            return -1 * cmp(unicode(a.committee), unicode(b.committee))


    roles = person.assignments.all()
    parent_mapping = {}
    for role in roles:
        if role.committee.committee_id:
            parent_mapping.setdefault(role.committee.committee_id, []).append(role)
    role_tree = []
    for role in roles:
        if not role.committee.committee:
            role.subroles = sorted([x for x in parent_mapping.get(role.committee.pk, [])],
                                   cmp=cmp_roles, reverse=True)
            role_tree.append(role)
    role_tree.sort(cmp=cmp_roles, reverse=True)
    return role_tree
