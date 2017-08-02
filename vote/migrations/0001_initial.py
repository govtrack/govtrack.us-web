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
            name='Vote',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('congress', models.IntegerField(help_text=b'The number of the Congress in which the vote took place. The current Congress is 115. In recent history Congresses are two years; however, this was not always the case.')),
                ('session', models.CharField(help_text=b'Within each Congress there are sessions. In recent history the sessions correspond to calendar years and are named accordingly. However, in historical data the sessions may be named in completely other ways, such as with letters A, B, and C. Session names are unique *within* a Congress.', max_length=4)),
                ('chamber', models.IntegerField(help_text=b'The chamber in which the vote was held, House or Senate.', choices=[(2, b'House'), (1, b'Senate')])),
                ('number', models.IntegerField(help_text=b'The number of the vote, unique to a Congress, session, and chamber.', verbose_name=b'Vote Number')),
                ('source', models.IntegerField(help_text=b'The source of the vote information.', choices=[(3, b'VoteView.com'), (2, b'house.gov'), (1, b'senate.gov')])),
                ('created', models.DateTimeField(help_text=b'The date (and in recent history also time) on which the vote was held.', db_index=True)),
                ('vote_type', models.CharField(help_text=b'Descriptive text for the type of the vote.', max_length=255)),
                ('category', models.IntegerField(help_text=b'The type of the vote.', max_length=255, choices=[(4, b'Cloture'), (7, b'Procedural'), (5, b'Passage (Part)'), (2, b'Passage under Suspension'), (12, b'Treaty Ratification'), (6, b'Nomination'), (9, b'Unknown Category'), (13, b'Impeachment'), (3, b'Passage'), (1, b'Amendment'), (10, b'Veto Override'), (11, b'Conviction')])),
                ('question', models.TextField(help_text=b'Descriptive text for what the vote was about.')),
                ('required', models.CharField(help_text=b"A code indicating what number of votes was required for success. Often '1/2' or '3/5'. This field should be interpreted with care. It comes directly from the upstream source and may need some 'unpacking.' For instance, while 1/2 always mean 1/2 of those voting (i.e. excluding absent and abstain), 3/5 in some cases means to include absent/abstain and in other cases to exclude.", max_length=10)),
                ('result', models.TextField(help_text=b'Descriptive text for the result of the vote.')),
                ('total_plus', models.IntegerField(help_text=b'The count of positive votes (aye/yea).', default=0, blank=True)),
                ('total_minus', models.IntegerField(help_text=b'The count of negative votes (nay/no).', default=0, blank=True)),
                ('total_other', models.IntegerField(help_text=b'The count of abstain or absent voters.', default=0, blank=True)),
                ('percent_plus', models.FloatField(help_text=b"The percent of positive votes. Null for votes that aren't yes/no (like election of the speaker, quorum calls).", blank=True, null=True)),
                ('margin', models.FloatField(help_text=b"The absolute value of the difference in the percent of positive votes and negative votes. Null for votes that aren't yes/no (like election of the speaker, quorum calls).", blank=True, null=True)),
                ('missing_data', models.BooleanField(help_text=b'If something in the source could be parsed and we should revisit the file.', default=False)),
                ('question_details', models.TextField(help_text=b'Additional descriptive text for what the vote was about.', blank=True, null=True)),
                ('related_amendment', models.ForeignKey(blank=True, null=True, help_text=b'A related amendment.', related_name=b'votes', on_delete=django.db.models.deletion.PROTECT, to='bill.Amendment')),
                ('related_bill', models.ForeignKey(blank=True, null=True, help_text=b'A related bill.', related_name=b'votes', on_delete=django.db.models.deletion.PROTECT, to='bill.Bill')),
            ],
            options={
                'ordering': ['created', 'chamber', 'number'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='VoteOption',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('key', models.CharField(max_length=20)),
                ('value', models.CharField(max_length=255)),
                ('vote', models.ForeignKey(related_name=b'options', to='vote.Vote')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Voter',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('voter_type', models.IntegerField(help_text=b'Whether the voter was a Member of Congress or the Vice President.', choices=[(2, b'Vice President'), (1, b'Unknown'), (3, b'Member of Congress')])),
                ('voteview_extra_code', models.CharField(help_text=b'Extra information provided in the voteview data.', max_length=20)),
                ('created', models.DateTimeField(help_text=b'The date (and in recent history also time) on which the vote was held.', db_index=True)),
                ('option', models.ForeignKey(help_text=b'How the person voted.', to='vote.VoteOption')),
                ('person', models.ForeignKey(blank=True, null=True, help_text=b'The person who cast this vote. May be null if the information could not be determined.', related_name=b'votes', on_delete=django.db.models.deletion.PROTECT, to='person.Person')),
                ('person_role', models.ForeignKey(blank=True, null=True, help_text=b'The role of the person who cast this vote at the time of the vote. May be null if the information could not be determined.', related_name=b'votes', on_delete=django.db.models.deletion.PROTECT, to='person.PersonRole')),
                ('vote', models.ForeignKey(help_text=b'The vote that this record is a part of.', related_name=b'voters', to='vote.Vote')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='VoteSummary',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('content', models.TextField(blank=True)),
                ('vote', models.OneToOneField(related_name=b'oursummary', on_delete=django.db.models.deletion.PROTECT, to='vote.Vote')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='vote',
            unique_together=set([('congress', 'chamber', 'session', 'number')]),
        ),
    ]
