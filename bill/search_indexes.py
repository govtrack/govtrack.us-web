import datetime
from haystack.indexes import *
from haystack import site
from bill.models import Bill
from search_sites import BaseIndex, register_model_for_search 

class BillIndex(BaseIndex):
    current_status_date = DateTimeField(model_attr='current_status_date')
    introduced_date = DateTimeField(model_attr='introduced_date')
    title = CharField(model_attr='title')
    titles = CharField(model_attr='titles')
    bill_type = IntegerField(model_attr='bill_type')
    congress = IntegerField(model_attr='congress')
    number = IntegerField(model_attr='number')
    current_status = IntegerField(model_attr='current_status')
    cosponsors = MultiValueField() 
    committees = MultiValueField() 
    terms = MultiValueField()

    def prepare_cosponsors(self, obj):
    	"""Prepare for foreign keys relationship objects.""" 
        return [p.fullname for p in obj.cosponsors.all()] 

    def prepare_committees(self, obj):
    	"""Prepare for foreign keys relationship objects.""" 
        return [c.name for c in obj.committees.all()]   

    def prepare_terms(self, obj):
    	"""Prepare for foreign keys relationship objects.""" 
        return [t.name for t in obj.terms.all()]

register_model_for_search(Bill, BillIndex)