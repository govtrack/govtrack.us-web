# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bill', '0001_initial'),
        ('committee', '0001_initial'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='committees',
            field=models.ManyToManyField(help_text=b'Committees to which the bill has been referred.', to='committee.Committee', related_name=b'bills'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='bill',
            name='cosponsors',
            field=models.ManyToManyField(help_text=b"The bill's cosponsors.", blank=True, through='bill.Cosponsor', to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='bill',
            name='sponsor',
            field=models.ForeignKey(blank=True, null=True, help_text=b'The primary sponsor of the bill.', related_name=b'sponsored_bills', on_delete=django.db.models.deletion.PROTECT, to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='bill',
            name='sponsor_role',
            field=models.ForeignKey(blank=True, null=True, help_text=b'The role of the primary sponsor of the bill at the time the bill was introduced.', on_delete=django.db.models.deletion.PROTECT, to='person.PersonRole'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='bill',
            name='terms',
            field=models.ManyToManyField(help_text=b'Subject areas associated with the bill.', to='bill.BillTerm', related_name=b'bills'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='bill',
            unique_together=set([('congress', 'bill_type', 'number'), ('congress', 'sliplawpubpriv', 'sliplawnum')]),
        ),
        migrations.AddField(
            model_name='amendment',
            name='bill',
            field=models.ForeignKey(help_text=b'The bill the amendment amends.', to='bill.Bill'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='amendment',
            name='sponsor',
            field=models.ForeignKey(blank=True, null=True, help_text=b'The sponsor of the amendment.', related_name=b'sponsored_amendments', on_delete=django.db.models.deletion.PROTECT, to='person.Person'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='amendment',
            name='sponsor_role',
            field=models.ForeignKey(blank=True, null=True, help_text=b'The role of the sponsor of the amendment at the time the amendment was offered.', on_delete=django.db.models.deletion.PROTECT, to='person.PersonRole'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='amendment',
            unique_together=set([('bill', 'sequence'), ('congress', 'amendment_type', 'number')]),
        ),
    ]
