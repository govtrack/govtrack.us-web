# -*- coding: utf-8 -*-
from django.db import models

from common import enum

class TermType(enum.Enum):
    old = enum.Item(1, 'Old')
    new = enum.Item(2, 'New')


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
