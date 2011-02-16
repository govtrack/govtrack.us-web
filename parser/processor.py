class Processor(object):
    FIELD_MAPPING = {}
    DEFAULT_VALUES = {}

    def check_required_key(self, key, node):
        """
        If key is required and does not exist in the XML node
        then raise Exception.
        """

        if key in self.REQUIRED_ATTRIBUTES:
            if not key in node.attrib:
                raise Exception('Did not found required attribute %s in record %s' % (
                    key, self.display_node(node)))

    def process(self, obj, node):
        for key in self.ATTRIBUTES:
            self.check_required_key(key, node)
            if key in node.attrib or key in self.DEFAULT_VALUES:
                field_name = self.FIELD_MAPPING.get(key, key)
                if key in node.attrib:
                    value = node.get(key)
                else:
                    value = self.DEFAULT_VALUES[key]
                setattr(obj, field_name, self.convert(key, value))
        return obj

    def display_node(self, node):
        return '<%s>: ' % node.tag + ', '.join('%s: %s' % x for x in node.attrib.iteritems())

    def convert(self, key, value):
        if hasattr(self, '%s_handler' % key):
            return getattr(self, '%s_handler' % key)(value)
        else:
            return value
