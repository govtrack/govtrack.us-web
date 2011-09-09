from haystack import indexes, autodiscover, site

class BaseIndex(indexes.SearchIndex):    
    text = indexes.CharField(document=True, use_template=True)



def register_model_for_search(model, index=BaseIndex):
    site.register(model, index)

autodiscover()