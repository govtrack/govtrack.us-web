# Generated by Django 2.2.28 on 2024-04-11 15:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0009_blogpost_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogpost',
            name='category',
            field=models.CharField(blank=True, choices=[('sitenews', 'News About GovTrack'), ('sitehelp', 'Using GovTrack Tips'), ('analysis', 'Analysis and Commentary'), ('billsumm', 'Bill Summary'), ('legrecap', 'Legislative Recap'), ('legahead', 'Legislative Preview')], max_length=24, null=True),
        ),
        migrations.AlterIndexTogether(
            name='blogpost',
            index_together={('published', 'created'), ('published', 'category', 'created')},
        ),
    ]
