from django.test import TestCase

from bill.models import BillType
from bill.title import get_primary_bill_title, get_secondary_bill_title

class BillMockup(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class BillTitleTestCase(TestCase):
    def test_title_calculation(self):
        bill = BillMockup(congress=112,
                          bill_type=BillType.house_of_representatives,
                          number=525)
        # Simple test
        titles = (('short', 'abc', 'title1'),)
        self.assertEqual('H.R. 525: title1', get_primary_bill_title(bill, titles))

        # Should be first title amoung titles with as="abc"
        titles = (('short', 'abc', 'title1'),
                  ('short', 'abc', 'title2'))
        self.assertEqual('H.R. 525: title1', get_primary_bill_title(bill, titles))

        # Should be title with short type
        titles = (('popular', 'abc', 'title1'),
                  ('short', 'abc', 'title2'))
        self.assertEqual('H.R. 525: title2', get_primary_bill_title(bill, titles))

        # Should be title with short type
        titles = (('popular', 'abc', 'title1'),
                  ('short', 'abc', 'title2'),
                  ('short', 'abc', 'title3'))
        self.assertEqual('H.R. 525: title2', get_primary_bill_title(bill, titles))

        # Should be first title in group of title with as=abc2
        titles = (('short', 'abc', 'title1'),
                  ('short', 'abc', 'title2'),
                  ('short', 'abc2', 'title3'),
                  ('short', 'abc2', 'title4'))
        self.assertEqual('H.R. 525: title3', get_primary_bill_title(bill, titles))

        # Should be title with official type
        titles = (('short', 'abc', 'title1'),
                  ('official', 'abc', 'title2'))
        self.assertEqual('title2', get_secondary_bill_title(bill, titles))

        # Should be None
        titles = (('official', 'abc', 'title2'),)
        self.assertEqual(None, get_secondary_bill_title(bill, titles))
