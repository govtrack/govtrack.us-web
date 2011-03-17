# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Person'
        db.create_table('person_person', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('firstname', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('lastname', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('middlename', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('birthday', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('gender', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('namemod', self.gf('django.db.models.fields.CharField')(max_length=10, blank=True)),
            ('nickname', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('bioguideid', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('pvsid', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('osid', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('metavidid', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('youtubeid', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('twitterid', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
        ))
        db.send_create_signal('person', ['Person'])

        # Adding model 'PersonRole'
        db.create_table('person_personrole', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('person', self.gf('django.db.models.fields.related.ForeignKey')(related_name='roles', to=orm['person.Person'])),
            ('role_type', self.gf('django.db.models.fields.IntegerField')()),
            ('current', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('startdate', self.gf('django.db.models.fields.DateField')()),
            ('enddate', self.gf('django.db.models.fields.DateField')()),
            ('senator_class', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('district', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('state', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('party', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('website', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
        ))
        db.send_create_signal('person', ['PersonRole'])


    def backwards(self, orm):
        
        # Deleting model 'Person'
        db.delete_table('person_person')

        # Deleting model 'PersonRole'
        db.delete_table('person_personrole')


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
            'enddate': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'party': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'person': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'roles'", 'to': "orm['person.Person']"}),
            'role_type': ('django.db.models.fields.IntegerField', [], {}),
            'senator_class': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'startdate': ('django.db.models.fields.DateField', [], {}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'website': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        }
    }

    complete_apps = ['person']
