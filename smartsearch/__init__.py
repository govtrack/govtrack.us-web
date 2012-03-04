from haystack import indexes

def build_haystack_index(model):
	class I(indexes.SearchIndex, indexes.Indexable):
		text = indexes.CharField(model_attr='get_index_text', document=True)
		indexed_model_name = indexes.CharField(default=model.__name__)
		def get_model(self):
			return model
			
	I.__name__ = model.__name__
			
	fieldmap = dict( (f.name, f) for f in model._meta.fields+model._meta.many_to_many )
	
	def build_field(fieldname):
		if not fieldname in fieldmap:
			raise ValueError("Model %s field %s in haystack_index does not exist." % (model.__name__, fieldname))
		field = fieldmap[fieldname]
		clz = field.__class__.__name__
		model_value = fieldname
		if hasattr(indexes, clz): # haystack has a index field with the same name as this field
			index_class = getattr(indexes, clz)
		elif clz == 'ForeignKey':
			index_class = indexes.IntegerField
			model_value += "_id"
		elif clz == 'ManyToManyField':
			index_class = indexes.MultiValueField
			model_value = "get_%s_index_list" % model_value
		else:
			raise ValueError("Model %s field %s in haystack_index is of a type I don't know how to index: %s." % (model.__name__, fieldname, clz))
		
		I.fields[fieldname] = index_class(model_attr=model_value, faceted=True, index_fieldname=fieldname, null=True) # stored=True, indexed=True,
			
	for index_field in getattr(model, "haystack_index", []):
		build_field(index_field)
	
	for fieldname, fieldtype in getattr(model, "haystack_index_extra", []):
		index_class = getattr(indexes, fieldtype + "Field")
		I.fields[fieldname] = index_class(model_attr=fieldname, faceted=True, index_fieldname=fieldname, null=True)
		
	return I
