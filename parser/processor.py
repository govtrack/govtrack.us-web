from datetime import datetime

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

    def process_keys(self, obj, node):
        "Process attributes of XML node"

        for key in self.ATTRIBUTES:
            if key in self.REQUIRED_ATTRIBUTES:
                if not key in node.attrib:
                    raise InvalidNode('Did not found required attribute %s in record %s' % (
                        key, self.display_node(node)))
            if key in node.attrib or key in self.DEFAULT_VALUES:
                field_name = self.FIELD_MAPPING.get(key, key)
                if key in node.attrib:
                    value = node.get(key)
                else:
                    value = self.DEFAULT_VALUES[key]
                setattr(obj, field_name, self.convert(key, value))

    def process_subnodes(self, obj, node):
        "Process subnodes of XML node"

        for key in self.NODES:
            try:
                subnode = node.xpath('./%s' % key)[0]
            except IndexError:
                if key in self.REQUIRED_NODES:
                    raise InvalidNode('Did not found required subnode %s in record %s' % (
                        key, self.display_node(node)))
                subnode = None
            if subnode is not None or key in self.DEFAULT_VALUES:
                field_name = self.FIELD_MAPPING.get(key, key)
                if subnode is not None:
                    value = unicode(subnode.text)
                else:
                    value = self.DEFAULT_VALUES[key]
                setattr(obj, field_name, self.convert(key, value))

    def process_text(self, obj, node):
        "Process text content of the XML node"

        pass

    def process(self, obj, node):
        self.process_keys(obj, node)
        self.process_subnodes(obj, node)
        self.process_text(obj, node)
        return obj

    def display_node(self, node):
        return '<%s>: ' % node.tag + ', '.join('%s: %s' % x for x in node.attrib.iteritems())

    def convert(self, key, value):
        key = key.replace("-", "_")
        if hasattr(self, '%s_handler' % key):
            return getattr(self, '%s_handler' % key)(value)
        else:
            return value

    def parse_datetime(self, value):
        try:
            return datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            try:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-05:00')
            except ValueError:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S-04:00')
                
    def changed(self, old_value, new_value):
        # Since new_value hasn't been touched except for the fields we've set on it,
        # we can use its __dict__, except Django ORM's _state field, to check if any
        # fields have changed.
        new_value.clean_fields() # normalize field values, like DateTimes that get reduced to Dates
        for k in new_value.__dict__:
            if k in ("id", "_state") or k.endswith("_cache"):
                continue
            if not hasattr(old_value, k) or getattr(old_value, k) != getattr(new_value, k):
                return True
        return False
        
