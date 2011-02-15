class Processor(object):
    FIELD_MAPPING = {}
    TYPO_MAPPING = {}

    def check_required_key(self, key, node):
        """
        If key is required and does not exist in the XML node
        then raise Exception.
        """

        if key in self.REQUIRED_ATTRIBUTES:
            if key in node.attrib:
                return
            if key in self.TYPO_MAPPING:
                key2 = self.TYPO_MAPPING[key]
                if key2 in node.attrib:
                    return
            raise Exception('Did not found required attribute %s in record %s' % (
                key, self.display_node(node)))

    def process(self, obj, node):
        # o_O
        # So we check here that XML node has all required attribute
        # If some attribute does not exist then we give it second chance:
        # some attributes are stored with misspelled name so we use TYPO_MAPPING
        # to check this
        for key in self.ATTRIBUTES:
            self.check_required_key(key, node)
            if key in node.attrib:
                field_name = self.FIELD_MAPPING.get(key, key)
                setattr(obj, field_name, self.convert(key, node.get(key)))
            else:
                if key in self.TYPO_MAPPING:
                    key2 = self.TYPO_MAPPING[key]
                    if key2 in node.attrib:
                        field_name = self.FIELD_MAPPING.get(key, key)
                        setattr(obj, field_name, self.convert(key, node.get(key2)))
        return obj

    def display_node(self, node):
        return '<%s>: ' % node.tag + ', '.join('%s: %s' % x for x in node.attrib.iteritems())

    def convert(self, key, value):
        if hasattr(self, '%s_handler' % key):
            return getattr(self, '%s_handler' % key)(value)
        else:
            return value
