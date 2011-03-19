"""
Smartsearch application tests.
"""
from django.test import TestCase
from django.db import models
from django import forms

from smartsearch.manager import SearchManager, Option, SmartChoiceField

RED = 1
GREEN = 2
BLUE = 3

COLORS = (
    (RED, 'Red'),
    (GREEN, 'Green'),
    (BLUE, 'Blue'),
)

COLOR_COUNTS = {
    RED: 1,
    GREEN: 3,
    BLUE: 5
}

class Thing(models.Model):
    color = models.IntegerField(choices=COLORS)

class RequestMockup(object):
    pass

class SearchTestCase(TestCase):
    def setUp(self):
        for color, count in COLOR_COUNTS.items():
            for x in xrange(count):
                Thing.objects.create(color=color)

    def test_setup(self):
        self.assertEqual(Thing.objects.filter(color=RED).count(),
                         COLOR_COUNTS[RED])

    def test_searchmanager(self):
        sm = SearchManager(Thing)
        sm.add_option('color')
        form = sm.form()
        self.assertTrue(
            isinstance(form.fields['color'], SmartChoiceField))
        for key, value in form.fields['color'].choices[1:]:
            value.endswith('(%d)' % COLOR_COUNTS[key])
        req = RequestMockup()
        req.GET = {'color': [str(RED)]}
        form = sm.form(req)
        qs = form.queryset()
        self.assertEqual(len(qs), COLOR_COUNTS[RED])
