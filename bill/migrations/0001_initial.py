# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Amendment',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('congress', models.IntegerField(help_text=b'The number of the Congress in which the amendment was offered. The current Congress is 115.')),
                ('amendment_type', models.IntegerField(help_text=b"The amendment's type, indicating the chmaber in which the amendment was offered.", choices=[(1, b'S.Amdt.'), (2, b'H.Amdt.'), (3, b'S.Up.Amdt.')])),
                ('number', models.IntegerField(help_text=b"The amendment's number according to the Library of Congress's H.Amdt and S.Amdt numbering (just the integer part).")),
                ('sequence', models.IntegerField(help_text=b'For House amendments, the sequence number of the amendment (unique within a bill).', blank=True, null=True)),
                ('title', models.CharField(help_text=b'A title for the amendment.', max_length=255)),
                ('offered_date', models.DateField(help_text=b'The date the amendment was offered.')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Bill',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('title', models.CharField(help_text=b"The bill's primary display title, including its number.", max_length=255)),
                ('lock_title', models.BooleanField(help_text=b'Whether the title has been manually overridden.', default=False)),
                ('titles', jsonfield.fields.JSONField(default=None)),
                ('bill_type', models.IntegerField(help_text=b"The bill's type (e.g. H.R., S., H.J.Res. etc.)", choices=[(6, b'S.Con.Res.'), (7, b'H.J.Res.'), (2, b'S.'), (5, b'H.Con.Res.'), (3, b'H.R.'), (8, b'S.J.Res.'), (4, b'S.Res.'), (1, b'H.Res.')])),
                ('congress', models.IntegerField(help_text=b'The number of the Congress in which the bill was introduced. The current Congress is 115.')),
                ('number', models.IntegerField(help_text=b"The bill's number (just the integer part).")),
                ('current_status', models.IntegerField(help_text=b'The current status of the bill.', choices=[(22, b'Vetoed & Senate Overrides (House Next)'), (7, b'Agreed To (Constitutional Amendment Proposal)'), (14, b'Failed to Resolve Differences'), (33, b'Enacted (Unknown Final Step)'), (2, b'Referred to Committee'), (16, b'Failed House'), (6, b'Agreed To (Simple Resolution)'), (19, b'Passed Senate, Failed House'), (15, b'Vetoed (No Override Attempt)'), (26, b'Vetoed & Override Passed Senate, Failed in House'), (24, b'Vetoed & Override Failed in House'), (17, b'Failed Senate'), (8, b'Agreed To (Concurrent Resolution)'), (23, b'Pocket Vetoed'), (27, b'Vetoed & Override Passed House, Failed in Senate'), (29, 'Enacted \u2014 Veto Overridden'), (31, b'Conference Report Agreed to by Senate'), (10, b'Passed House with Changes'), (4, b'Passed House'), (12, b'Failed Under Suspension'), (21, b'Vetoed & House Overrides (Senate Next)'), (3, b'Ordered Reported by Committee'), (32, 'Enacted \u2014 By 10 Day Rule'), (9, b'Passed House & Senate'), (30, b'Conference Report Agreed to by House'), (1, b'Introduced'), (5, b'Passed Senate'), (25, b'Vetoed & Override Failed in Senate'), (11, b'Passed Senate with Changes'), (28, 'Enacted \u2014 Signed by the President'), (20, b'Passed House, Failed Senate'), (13, b'Failed Cloture')])),
                ('current_status_date', models.DateField(help_text=b'The date of the last major action on the bill corresponding to the current_status.')),
                ('introduced_date', models.DateField(help_text=b'The date the bill was introduced.')),
                ('major_actions', jsonfield.fields.JSONField(default=[])),
                ('committee_reports', jsonfield.fields.JSONField(help_text=b'serialized list of committee report citations', default=[], blank=True, null=True)),
                ('sliplawpubpriv', models.CharField(help_text=b'For enacted laws, whether the law is a public (PUB) or private (PRI) law. Unique with congress and sliplawnum.', max_length=3, blank=True, null=True, choices=[(b'PUB', b'Public'), (b'PRI', b'Private')])),
                ('sliplawnum', models.IntegerField(help_text=b'For enacted laws, the slip law number (i.e. the law number in P.L. XXX-123). Unique with congress and sliplawpublpriv.', blank=True, null=True)),
                ('source', models.CharField(help_text=b"The primary source for this bill's metadata.", max_length=16, choices=[(b'thomas-congproj', b'THOMAS.gov (via Congress Project)'), (b'statutesatlarge', b'U.S. Statutes at Large'), (b'americanmemory', b'LoC American Memory Collection')])),
                ('source_link', models.CharField(help_text=b"When set, a link to the page on the primary source website for this bill. Set when source='americanmemory' only.", max_length=256, blank=True, null=True)),
                ('docs_house_gov_postdate', models.DateTimeField(help_text=b'The date on which the bill was posted to http://docs.house.gov (which is different from the date it was expected to be debated).', blank=True, null=True)),
                ('senate_floor_schedule_postdate', models.DateTimeField(help_text=b'The date on which the bill was posted on the Senate Floor Schedule (which is different from the date it was expected to be debated).', blank=True, null=True)),
                ('scheduled_consideration_date', models.DateTimeField(help_text=b'The date on which the bill is expected to be considered on the floor for the most recent of docs_house_gov_postdate and senate_floor_schedule_postdate, and if for docs.house.gov it is the week that this is the Monday of.', blank=True, null=True)),
                ('text_incorporation', jsonfield.fields.JSONField(help_text=b'What enacted bills have provisions of this bill been incorporated into?', default=[], blank=True, null=True)),
            ],
            options={
                'ordering': ('congress', 'bill_type', 'number'),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BillLink',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('url', models.CharField(max_length=256)),
                ('title', models.CharField(max_length=256)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('approved', models.BooleanField(default=False)),
                ('bill', models.ForeignKey(related_name=b'links', on_delete=django.db.models.deletion.PROTECT, to='bill.Bill')),
            ],
            options={
                'ordering': ('-created',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BillSummary',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('content', models.TextField(blank=True)),
                ('source_url', models.TextField(blank=True, null=True)),
                ('source_text', models.CharField(max_length=64, blank=True, null=True, db_index=True)),
                ('bill', models.OneToOneField(related_name=b'oursummary', on_delete=django.db.models.deletion.PROTECT, to='bill.Bill')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BillTerm',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('term_type', models.IntegerField(choices=[(2, b'New'), (1, b'Old')])),
                ('name', models.CharField(max_length=255)),
                ('subterms', models.ManyToManyField(blank=True, to='bill.BillTerm', related_name=b'parents')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BillTextComparison',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('ver1', models.CharField(max_length=6)),
                ('ver2', models.CharField(max_length=6)),
                ('data', jsonfield.fields.JSONField()),
                ('bill1', models.ForeignKey(related_name=b'comparisons1', to='bill.Bill')),
                ('bill2', models.ForeignKey(related_name=b'comparisons2', to='bill.Bill')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Cosponsor',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('joined', models.DateField(help_text=b"The date the cosponsor was added. It is always greater than or equal to the bill's introduced_date.", db_index=True)),
                ('withdrawn', models.DateField(help_text=b'If the cosponsor withdrew his/her support, the date of withdrawl. Otherwise empty.', blank=True, null=True)),
                ('bill', models.ForeignKey(help_text=b'The bill being cosponsored.', to='bill.Bill')),
                ('person', models.ForeignKey(help_text=b'The cosponsoring person.', on_delete=django.db.models.deletion.PROTECT, to='person.Person')),
                ('role', models.ForeignKey(help_text=b'The role of the cosponsor at the time of cosponsorship.', on_delete=django.db.models.deletion.PROTECT, to='person.PersonRole')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RelatedBill',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('relation', models.CharField(max_length=16)),
                ('bill', models.ForeignKey(related_name=b'relatedbills', to='bill.Bill')),
                ('related_bill', models.ForeignKey(related_name=b'relatedtobills', to='bill.Bill')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='USCSection',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('citation', models.CharField(max_length=32, blank=True, null=True, db_index=True)),
                ('level_type', models.CharField(max_length=10, choices=[(b'title', b'Title'), (b'subtitle', b'Subtitle'), (b'chapter', b'Chapter'), (b'subchapter', b'Subchapter'), (b'part', b'Part'), (b'subpart', b'Subpart'), (b'division', b'Division'), (b'heading', b'Heading'), (b'section', b'Section')])),
                ('number', models.CharField(max_length=24, blank=True, null=True)),
                ('deambig', models.IntegerField(default=0)),
                ('name', models.TextField(blank=True, null=True)),
                ('ordering', models.IntegerField()),
                ('update_flag', models.IntegerField(default=0)),
                ('parent_section', models.ForeignKey(blank=True, null=True, to='bill.USCSection')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='cosponsor',
            unique_together=set([('bill', 'person')]),
        ),
        migrations.AlterUniqueTogether(
            name='billtextcomparison',
            unique_together=set([('bill1', 'ver1', 'bill2', 'ver2')]),
        ),
        migrations.AlterUniqueTogether(
            name='billterm',
            unique_together=set([('name', 'term_type')]),
        ),
        migrations.AlterUniqueTogether(
            name='billlink',
            unique_together=set([('bill', 'url')]),
        ),
    ]
