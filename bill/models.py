# -*- coding: utf-8 -*-
from django.db import models

from common import enum
from common.fields import JSONField

from committee.models import Committee

"Enums"

class BillType(enum.Enum):
    house_resolution = enum.Item(1, 'H.Res.', slug='hres', xml_code='hr')
    senate = enum.Item(2, 'S', slug='s', xml_code='s')
    house_of_representatives = enum.Item(3, 'H.R.', slug='hr', xml_code='h')
    senate_resolution = enum.Item(4, 'S.Res.', slug='sr', xml_code='sr')
    house_concurrent_resolution = enum.Item(5, 'H.Con.Res.', slug='hc', xml_code='hc')
    senate_concurrent_resolution = enum.Item(6, 'S.Con.Res.', slug='sc', xml_code='sc')
    house_joint_resolution = enum.Item(7, 'H.J.Res.', slug='hj', xml_code='hj')
    senate_joint_resolution = enum.Item(8, 'S.J.Res.', slug='sj', xml_code='sj')


class TermType(enum.Enum):
    old = enum.Item(1, 'Old')
    new = enum.Item(2, 'New')


"Models"

class BillTerm(models.Model):
    """
    Bill Term aka Issua Area

    Old terms:
     * http://www.govtrack.us/data/us/liv.xml
    New terms:
     * http://www.govtrack.us/data/us/liv111.xml
     * http://www.govtrack.us/data/us/crsnet.xml
    """
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('bill.BillTerm', blank=True, null=True)
    term_type = models.IntegerField(choices=TermType)

    def __unicode__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'parent', 'term_type')


class Bill(models.Model):
    title = models.CharField(max_length=255)
    # Serialized list of all bill titles
    titles = JSONField()
    bill_type = models.IntegerField(choices=BillType)
    congress = models.IntegerField()
    number = models.IntegerField()
    sponsor = models.ForeignKey('person.Person', blank=True, null=True,
                                related_name='sponsored_bills')
    committees = models.ManyToManyField(Committee, related_name='bills')
    terms = models.ManyToManyField(BillTerm, related_name='bills')
    # status = models.CharField(max_lenght=255)
    # status_date = models.DateField()
    cosponsor_count = models.IntegerField(blank=True, null=True)
    # action ???

    def __unicode__(self):
        return self.title

    class Meta:
        ordering = ('congress', 'bill_type', 'number')
        unique_together = ('congress', 'bill_type', 'number')
