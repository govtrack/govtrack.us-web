from haystack import indexes
from datetime import datetime

# Some of the dates in Solr (Bill.current_status_date) are coming back as a DateTime, which Haystack rejects.
class MyDateField(indexes.DateField):
	def convert(self, value):
		d = indexes.DateTimeField().convert(value)
		if isinstance(d, datetime): d = d.date()
		return d
indexes.DateField = MyDateField

def build_haystack_index(model):
	class I(indexes.SearchIndex, indexes.Indexable):
		text = indexes.CharField(model_attr='get_index_text', document=True)
		text_boosted = indexes.CharField(model_attr='get_index_text_boosted', boost=2.0)
		indexed_model_name = indexes.CharField(default=model.__name__)
		def get_model(self):
			return model
		def index_queryset(self, using=None):
			return model.objects.prefetch_related(*self.prefetch_related_list)
			
	I.__name__ = model.__name__
	I.prefetch_related_list = []
			
	fieldmap = dict( (f.name, f) for f in model._meta.get_fields() )
	
	def build_field(model_field, index_field):
		if not model_field in fieldmap:
			raise ValueError("Model %s field %s in haystack_index does not exist." % (model.__name__, model_field))
		field = fieldmap[model_field]
		clz = field.__class__.__name__
		model_value = model_field
		if hasattr(indexes, clz): # haystack has a index field with the same name as this field
			index_class = getattr(indexes, clz)
		elif clz == 'ForeignKey':
			index_class = indexes.IntegerField
			model_value += "_id"
			I.prefetch_related_list.append(model_field)
		elif clz == 'ManyToManyField':
			index_class = indexes.MultiValueField
			model_value = "get_%s_index_list" % model_value
			I.prefetch_related_list.append(model_field)
		else:
			raise ValueError("Model %s field %s in haystack_index is of a type I don't know how to index: %s." % (model.__name__, model_field, clz))
		
		I.fields[index_field] = index_class(model_attr=model_value, faceted=True, index_fieldname=index_field, null=True, indexed=True) # xapian requires indexed=True, elasticsearch requires indexed=False to turn off language analysis, and Solr seems to ignore
		I.fields[index_field].set_instance_name(index_field)
			
	for index_field in getattr(model, "haystack_index", []):
		model_field = index_field
		if ">" in index_field: model_field, index_field = index_field.split(">")
		build_field(model_field, index_field)
	
	for index_field, fieldtype in getattr(model, "haystack_index_extra", []):
		index_class = getattr(indexes, fieldtype + "Field")
		model_field = index_field
		if ">" in index_field: model_field, index_field = index_field.split(">")
		I.fields[index_field] = index_class(model_attr=model_field, faceted=True, index_fieldname=index_field, null=True, indexed=True) # see note above about indexed
		
	return I
