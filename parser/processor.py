from datetime import datetime
from pprint import pformat

class InvalidNode(Exception):
    """
    Raised when XML Node contains invalid data.
    """

class Processor(object):
    REQUIRED_ATTRIBUTES = []
    ATTRIBUTES = []
    REQUIRED_NODES = []
    NODES = []
    FIELD_MAPPING = {}
    DEFAULT_VALUES = {}

    def process_attributes(self, obj, node):
        "Process attributes of XML node"

        attrib = self.get_node_attribute_keys(node)

        for key in self.ATTRIBUTES:
            if key in self.REQUIRED_ATTRIBUTES:
                if not key in attrib:
                    raise InvalidNode('Did not found required attribute %s in record %s' % (
                        key, self.display_node(node)))
            if key in attrib or key in self.DEFAULT_VALUES:
                field_name = self.FIELD_MAPPING.get(key, key)
                if key in attrib:
                    value = self.get_node_attribute_value(node, key)
                else:
                    value = self.DEFAULT_VALUES[key]
                setattr(obj, field_name, self.convert(key, value))

    def process_subnodes(self, obj, node):
        "Process subnodes of XML node"

        for key in self.NODES:
            try:
                subnode = self.get_node_child_value(node, key)
            except IndexError:
                if key in self.REQUIRED_NODES:
                    raise InvalidNode('Did not found required subnode %s in record %s' % (
                        key, self.display_node(node)))
                subnode = None
            if subnode is not None or key in self.DEFAULT_VALUES:
                field_name = self.FIELD_MAPPING.get(key, key)
                if subnode is not None:
                    value = subnode
                else:
                    value = self.DEFAULT_VALUES[key]
                setattr(obj, field_name, self.convert(key, value))

    def process_text(self, obj, node):
        "Process text content of the XML node"
        pass

    def process(self, obj, node):
        self.process_attributes(obj, node)
        self.process_subnodes(obj, node)
        self.process_text(obj, node)
        return obj

    def convert(self, key, value):
        key = key.replace("-", "_")
        if hasattr(self, '%s_handler' % key):
            return getattr(self, '%s_handler' % key)(value)
        else:
            return value

    @staticmethod
    def parse_datetime(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            try:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-05:00')
            except ValueError:
                try:
                    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-04:00')
                except ValueError:
                    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')

    def is_model_field(self, obj, fieldname):
        from django.db.models import FieldDoesNotExist
        try:
            return obj._meta.get_field(fieldname) is not None # =! None breaks because of operator overloading
        except FieldDoesNotExist:
            return False

    def changed(self, old_value, new_value):
        # Since new_value hasn't been touched except for the fields we've set on it,
        # we can use its __dict__, except Django ORM's _state field, to check if any
        # fields have changed.
        new_value.clean_fields() # normalize field values, like DateTimes that get reduced to Dates
        for k in new_value.__dict__:
            if k != "id" and self.is_model_field(old_value, k):
                v1 = getattr(old_value, k)
                v2 = getattr(new_value, k)
                if v1 != v2:
                    print "Change in", k, "value of", unicode(old_value).encode("utf8"), ":", unicode(v1).encode("utf8"), "=>", unicode(v2).encode("utf8")
                    return True
        return False

class XmlProcessor(Processor):
    def display_node(self, node):
        return '<%s>: ' % node.tag + ', '.join('%s: %s' % x for x in node.attrib.iteritems())
    def get_node_attribute_keys(self, node):
        return node.attrib
    def get_node_attribute_value(self, node, attr):
        return node.get(attr)
    def get_node_child_value(self, node, name):
        # raise IndexError on failure
        subnode = node.xpath('./%s' % name)[0]
        return unicode(subnode.text)

class YamlProcessor(Processor):
    def display_node(self, node):
        return pformat(node)
    def get_node_attribute_keys(self, node):
        # handle a__b path names by scanning node recursively
        ret = set()
        for k, v in node.items():
            ret.add(k)
            if isinstance(v, dict):
                for k2 in self.get_node_attribute_keys(v):
                    ret.add(k + '__' + k2)
        return ret
    def get_node_attribute_value(self, node, attr):
        for k in attr.split('__'):
            node = node.get(k, None)
        return node
    def get_node_child_value(self, node, name):
        raise Exception("Not available for YAML files.")

def yaml_load(path):
    # Loading YAML is ridiculously slow. In congress-legislators's
    # utils, we cache the YAML in a pickled file which is a lot
    # faster. This has to match the utils file there since we'll
    # overwrite their file when we save the pickle cache...

    import cPickle as pickle, os.path, hashlib
    import yaml
    try:
        from yaml import CSafeLoader as Loader, CDumper as Dumper
    except ImportError:
        from yaml import SafeLoader as Loader, Dumper

    # Check if the .pickle file exists and a hash stored inside it
    # matches the hash of the YAML file, and if so unpickle it.
    h = hashlib.sha1(open(path).read()).hexdigest()
    if os.path.exists(path + ".pickle"):
        store = pickle.load(open(path + ".pickle"))
        if store["hash"] == h:
            return store["data"]

    # No cached pickled data exists, so load the YAML file.
    data = yaml.load(open(path), Loader=Loader)

    # Store in a pickled file for fast access later.
    pickle.dump({ "hash": h, "data": data }, open(path+".pickle", "w"))

    return data

