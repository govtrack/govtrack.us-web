# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding index on 'PersonRole', fields ['startdate']
        db.create_index('person_personrole', ['startdate'])

        # Adding index on 'PersonRole', fields ['enddate']
        db.create_index('person_personrole', ['enddate'])


    def backwards(self, orm):
        
        # Removing index on 'PersonRole', fields ['enddate']
        db.delete_index('person_personrole', ['enddate'])

        # Removing index on 'PersonRole', fields ['startdate']
        db.delete_index('person_personrole', ['startdate'])


    models = {
        'person.person': {
            'Meta': {'object_name': 'Person'},
            'bioguideid': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'birthday': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'firstname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'gender': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lastname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'metavidid': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'middlename': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'namemod': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'}),
            'nickname': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'osid': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'pvsid': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'twitterid': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'youtubeid': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        'person.personrole': {
            'Meta': {'ordering': "['startdate']", 'object_name': 'PersonRole'},
            'current': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'district': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'enddate': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'party': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'roles'", 'to': "orm['person.Person']"}),
            'role_type': ('django.db.models.fields.IntegerField', [], {}),
            'senator_class': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'startdate': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'website': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        }
    }

    complete_apps = ['person']
