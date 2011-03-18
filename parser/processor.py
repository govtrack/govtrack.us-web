from datetime import datetime

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
                    raise Exception('Did not found required attribute %s in record %s' % (
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
                    raise Exception('Did not found required subnode %s in record %s' % (
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
