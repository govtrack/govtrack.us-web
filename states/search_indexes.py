from models import StateBill
from smartsearch import build_haystack_index

StateBillIndex = build_haystack_index(StateBill)

