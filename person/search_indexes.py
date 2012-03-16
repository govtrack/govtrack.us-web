from models import Person
from smartsearch import build_haystack_index

PersonIndex = build_haystack_index(Person)


