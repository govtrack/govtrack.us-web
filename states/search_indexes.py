from models import StateBill
from smartsearch import build_haystack_index
from haystack.routers import BaseRouter

StateBillIndex = build_haystack_index(StateBill)

class MyRouter(BaseRouter):
    def for_read(self, **hints):
        raise ValueError(repr(hints))
        return None

    def for_write(self, **hints):
        raise ValueError(repr(hints))
        return None
