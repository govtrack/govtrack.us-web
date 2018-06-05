from .models import Bill
from smartsearch import build_haystack_index

BillIndex = build_haystack_index(Bill)

