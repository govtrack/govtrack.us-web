# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('firstname', models.CharField(help_text=b"The person's first name or first initial.", max_length=255)),
                ('lastname', models.CharField(help_text=b"The person's last name.", max_length=255)),
                ('middlename', models.CharField(help_text=b"The person's middle name (optional).", max_length=255, blank=True)),
                ('birthday', models.DateField(help_text=b"The person's birthday.", blank=True, null=True)),
                ('gender', models.IntegerField(help_text=b"The person's gender, if known. For historical data, the gender is sometimes not known.", blank=True, null=True, choices=[(2, b'Female'), (1, b'Male')])),
                ('namemod', models.CharField(help_text=b"The suffix on the person's name usually one of Jr., Sr., I, II, etc.", max_length=10, blank=True)),
                ('nickname', models.CharField(help_text=b'The person\'s nickname. If set, the nickname should usually be displayed in quotes where a middle name would go. For instance, Joe "Buster" Smith.', max_length=255, blank=True)),
                ('bioguideid', models.CharField(help_text=b"The person's ID on bioguide.congress.gov. May be null if the person served only as a president and not in Congress.", max_length=255, blank=True, null=True)),
                ('pvsid', models.CharField(help_text=b"The person's ID on vote-smart.org (Project Vote Smart), if known.", max_length=255, blank=True, null=True)),
                ('osid', models.CharField(help_text=b"The person's ID on opensecrets.org (The Center for Responsive Politics), if known.", max_length=255, blank=True, null=True)),
                ('youtubeid', models.CharField(help_text=b"The name of the person's official YouTube channel, if known.", max_length=255, blank=True, null=True)),
                ('twitterid', models.CharField(help_text=b"The name of the person's official Twitter handle, if known.", max_length=50, blank=True, null=True)),
                ('cspanid', models.IntegerField(help_text=b'The ID of the person on CSPAN websites, if known.', blank=True, null=True)),
                ('name', models.CharField(help_text=b"The person's full name with title, district, and party information for current Members of Congress, in a typical display format.", max_length=96)),
                ('sortname', models.CharField(help_text=b"The person's name suitable for sorting lexicographically by last name or for display in a sorted list of names. Title, district, and party information are included for current Members of Congress.", max_length=64)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PersonRole',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('role_type', models.IntegerField(help_text=b'The type of this role: a U.S. senator, a U.S. congressperson, a U.S. president, or a U.S. vice president.', db_index=True, choices=[(4, b'Vice President'), (2, b'Representative'), (3, b'President'), (1, b'Senator')])),
                ('current', models.BooleanField(help_text=b'Whether the role is currently held, or if this is archival information.', default=False, db_index=True, choices=[(False, b'No'), (True, b'Yes')])),
                ('startdate', models.DateField(help_text=b'The date the role began (when the person took office).', db_index=True)),
                ('enddate', models.DateField(help_text=b'The date the role ended (when the person resigned, died, etc.)', db_index=True)),
                ('senator_class', models.IntegerField(help_text=b'For senators, their election class, which determines which years they are up for election. (It has nothing to do with seniority.)', blank=True, null=True, choices=[(1, b'Class 1'), (2, b'Class 2'), (3, b'Class 3')], db_index=True)),
                ('senator_rank', models.IntegerField(help_text=b'For senators, their state rank, i.e. junior or senior. For historical data, this is their last known rank.', blank=True, null=True, choices=[(1, b'Senior'), (2, b'Junior')])),
                ('district', models.IntegerField(help_text=b'For representatives, the number of their congressional district. 0 for at-large districts, -1 in historical data if the district is not known.', blank=True, null=True, db_index=True)),
                ('state', models.CharField(help_text=b'For senators and representatives, the two-letter USPS abbrevation for the state or territory they are serving. Values are the abbreviations for the 50 states (each of which have at least one representative and two senators, assuming no vacancies) plus DC, PR, and the island territories AS, GU, MP, and VI (all of which have a non-voting delegate), and for really old historical data you will also find PI (Philippines, 1907-1946), DK (Dakota Territory, 1861-1889), and OR (Orleans Territory, 1806-1811) for non-voting delegates.', max_length=2, blank=True, db_index=True, choices=[(b'AK', b'Alaska'), (b'AL', b'Alabama'), (b'AR', b'Arkansas'), (b'AS', b'American Samoa'), (b'AZ', b'Arizona'), (b'CA', b'California'), (b'CO', b'Colorado'), (b'CT', b'Connecticut'), (b'DC', b'District of Columbia'), (b'DE', b'Delaware'), (b'DK', b'Dakota Territory'), (b'FL', b'Florida'), (b'GA', b'Georgia'), (b'GU', b'Guam'), (b'HI', b'Hawaii'), (b'IA', b'Iowa'), (b'ID', b'Idaho'), (b'IL', b'Illinois'), (b'IN', b'Indiana'), (b'KS', b'Kansas'), (b'KY', b'Kentucky'), (b'LA', b'Louisiana'), (b'MA', b'Massachusetts'), (b'MD', b'Maryland'), (b'ME', b'Maine'), (b'MI', b'Michigan'), (b'MN', b'Minnesota'), (b'MO', b'Missouri'), (b'MP', b'Northern Mariana Islands'), (b'MS', b'Mississippi'), (b'MT', b'Montana'), (b'NC', b'North Carolina'), (b'ND', b'North Dakota'), (b'NE', b'Nebraska'), (b'NH', b'New Hampshire'), (b'NJ', b'New Jersey'), (b'NM', b'New Mexico'), (b'NV', b'Nevada'), (b'NY', b'New York'), (b'OH', b'Ohio'), (b'OK', b'Oklahoma'), (b'OL', b'Territory of Orleans'), (b'OR', b'Oregon'), (b'PA', b'Pennsylvania'), (b'PI', b'Philippines'), (b'PR', b'Puerto Rico'), (b'RI', b'Rhode Island'), (b'SC', b'South Carolina'), (b'SD', b'South Dakota'), (b'TN', b'Tennessee'), (b'TX', b'Texas'), (b'UT', b'Utah'), (b'VA', b'Virginia'), (b'VI', b'Virgin Islands'), (b'VT', b'Vermont'), (b'WA', b'Washington'), (b'WI', b'Wisconsin'), (b'WV', b'West Virginia'), (b'WY', b'Wyoming')])),
                ('party', models.CharField(help_text=b'The political party of the person. If the person changes party, it is usually the most recent party during this role.', max_length=255, blank=True, null=True, db_index=True)),
                ('caucus', models.CharField(help_text=b'For independents, the party that the legislator caucuses with. If changed during a term, the most recent.', max_length=255, blank=True, null=True)),
                ('website', models.CharField(help_text=b'The URL to the official website of the person during this role, if known.', max_length=255, blank=True)),
                ('phone', models.CharField(help_text=b'The last known phone number of the DC congressional office during this role, if known.', max_length=64, blank=True, null=True)),
                ('leadership_title', models.CharField(help_text=b'The last known leadership role held during this role, if any.', max_length=255, blank=True, null=True)),
                ('extra', jsonfield.fields.JSONField(help_text=b'Additional schema-less information stored with this object.', blank=True, null=True)),
                ('person', models.ForeignKey(related_name=b'roles', to='person.Person')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
