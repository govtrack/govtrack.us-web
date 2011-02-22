from committee.util import sort_members
from committee.models import CommitteeMemberRole

def get_committee_assignments(person):
    """
    Find committee assignments for the given person
    in current congress.

    Returns sorted list of CommitteeMemberRole objects where each object is
    committee assinment which could has subcommittee assignments in ``subroles`` attribute.
    """

    roles = person.assignments.all()
    parent_mapping = {}
    for role in roles:
        if role.committee.committee_id:
            parent_mapping.setdefault(role.committee.committee_id, []).append(role)
    role_tree = []
    for role in roles:
        if not role.committee.committee:
            role.subroles = sort_members([x for x in parent_mapping.get(role.committee.pk, [])])
            role_tree.append(role)
    role_tree = sort_members(role_tree)
    return role_tree
