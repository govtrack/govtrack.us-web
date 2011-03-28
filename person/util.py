from datetime import datetime

from committee.util import sort_members
from committee.models import CommitteeMemberRole
from person.models import PersonRole

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


def load_roles_at_date(persons, when=datetime.now()):
    """
    Find out role of each person at given date.

    This method is optimized for bulk operation.
    """

    roles = PersonRole.objects.filter(startdate__lte=when, enddate__gte=when).select_related('person')
    roles_by_person = {}
    for role in roles:
        roles_by_person[role.person] = role
    for person in persons:
        person.role = roles_by_person.get(person)
        person._cached_roles.add(person.role)
    return None 
