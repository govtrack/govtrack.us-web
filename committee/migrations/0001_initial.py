# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bill', '0001_initial'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Committee',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('committee_type', models.IntegerField(help_text=b'Whether this is a House, Senate, or Joint committee.', blank=True, null=True, choices=[(2, b'Joint'), (1, b'Senate'), (3, b'House')])),
                ('code', models.CharField(help_text=b'An alphanumeric code used for the committee on THOMAS.gov, House.gov, and Senate.gov.', max_length=10, db_index=True, unique=True)),
                ('name', models.CharField(help_text=b"The name of the committee or subcommittee. Committee names typically look like '{House,Senate} Committee on ...', while subcommmittee names look like 'Legislative Branch'.", max_length=255)),
                ('url', models.CharField(help_text=b"The committee's website.", max_length=255, blank=True, null=True)),
                ('abbrev', models.CharField(help_text=b'A really short abbreviation for the committee. Has no special significance.', max_length=255, blank=True)),
                ('obsolete', models.BooleanField(help_text=b'True if this committee no longer exists.', default=False, db_index=True)),
                ('jurisdiction', models.TextField(help_text=b"The committee's jurisdiction, if known.", blank=True, null=True)),
                ('jurisdiction_link', models.TextField(help_text=b'A link to where the jurisdiction text was sourced from.', blank=True, null=True)),
                ('committee', models.ForeignKey(blank=True, null=True, help_text=b'This field indicates whether the object is a commmittee, in which case the committee field is null, or a subcommittee, in which case this field gives the parent committee.', related_name=b'subcommittees', on_delete=django.db.models.deletion.PROTECT, to='committee.Committee')),
            ],
            options={
                'ordering': ['name'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CommitteeMeeting',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('when', models.DateTimeField()),
                ('subject', models.TextField()),
                ('guid', models.CharField(max_length=36, db_index=True, unique=True)),
                ('room', models.TextField(null=True)),
                ('bills', models.ManyToManyField(blank=True, to='bill.Bill')),
                ('committee', models.ForeignKey(related_name=b'meetings', to='committee.Committee')),
            ],
            options={
                'ordering': ['-created'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CommitteeMember',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('role', models.IntegerField(help_text=b'The role of the member on the committee.', default=5, choices=[(4, b'Vice Chair'), (2, b'Chair'), (3, b'Ranking Member'), (5, b'Member'), (1, b'Ex Officio')])),
                ('committee', models.ForeignKey(help_text=b'The committee or subcommittee being served on.', related_name=b'members', to='committee.Committee')),
                ('person', models.ForeignKey(help_text=b'The Member of Congress serving on a committee.', related_name=b'committeeassignments', to='person.Person')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
