if __name__ == "__main__":
	import sys, os
	sys.path.insert(0, "..")
	sys.path.insert(0, ".")
	sys.path.insert(0, "lib")
	sys.path.insert(0, ".env/lib/python2.7/site-packages")
	os.environ["DJANGO_SETTINGS_MODULE"] = 'settings'

import datetime, lxml

from bill.models import BillType

bill_gpo_status_codes = {
	"ah": "Amendment",
	"ah2": "Amendment",
	"as": "Amendment",
	"as2": "Amendment",
	"ash": "Additional Sponsors",
	"sas": "Additional Sponsors",
	"sc": "Sponsor Change",
	"ath": "Resolution Agreed to",
	"ats": "Resolution Agreed to",
	"cdh": "Committee Discharged",
	"cds": "Committee Discharged",
	"cph": "Considered and Passed by the House",
	"cps": "Considered and Passed by the Senate",
	"eah": "Passed the House (Engrossed) with an Amendment",
	"eas": "Passed the Senate (Engrossed) with an Amendment",
	"eh": "Passed the House (Engrossed)",
	"ehr": "Passed the House (Engrossed)/Reprint",
	"eh_s": "Passed the House (Engrossed)/Star Print",
	"enr": "Passed Congress/Enrolled Bill",
	"renr": "Passed Congress/Re-enrolled",
	"es": "Passed the Senate (Engrossed)",
	"esr": "Passed the Senate (Engrossed)/Reprint",
	"es_s": "Passed the Senate (Engrossed)/Star Print",
	"fah": "Failed Amendment",
	"fps": "Failed Passage",
	"hdh": "Held at Desk in the House",
	"hds": "Held at Desk in the Senate",
	"ih": "Introduced",
	"ihr": "Introduced/Reprint",
	"ih_s": "Introduced/Star Print",
	"is": "Introduced",
	"isr": "Introduced/Reprint",
	"is_s": "Introduced/Star Print",
	"iph": "Indefinitely Postponed in the House",
	"ips": "Indefinitely Postponed in the Senate",
	"lth": "Laid on Table in the House",
	"lts": "Laid on Table in the Senate",
	"oph": "Ordered to be Printed",
	"ops": "Ordered to be Printed",
	"pch": "Placed on Calendar in the House",
	"pcs": "Placed on Calendar in the Senate",
	"pp": "Public Print",
	"rah": "Referred to House Committee (w/ Amendments)",
	"ras": "Referred to Senate Committee (w/ Amendments)",
	"rch": "Reference Change",
	"rcs": "Reference Change",
	"rdh": "Received by the House",
	"rds": "Received by the Senate",
	"reah": "Passed the House (Re-Engrossed) with an Amendment",
	"re": "Reprint of an Amendment",
	"res": "Passed the Senate (Re-Engrossed) with an Amendment",
	"rfh": "Referred to House Committee",
	"rfhr": "Referred to House Committee/Reprint",
	"rfh_s": "Referred to House Committee/Star Print",
	"rfs": "Referred to Senate Committee",
	"rfsr": "Referred to Senate Committee/Reprint",
	"rfs_s": "Referred to Senate Committee/Star Print",
	"rh": "Reported by House Committee",
	"rhr": "Reported by House Committee/Reprint",
	"rh_s": "Reported by House Committee/Star Print",
	"rs": "Reported by Senate Committee",
	"rsr": "Reported by Senate Committee/Reprint",
	"rs_s": "Reported by Senate Committee/Star Print",
	"rih": "Referral Instructions in the House",
	"ris": "Referral Instructions in the Senate",
	"rth": "Referred to House Committee",
	"rts": "Referred to Senate Committee",
	"s_p": "Star Print of an Amendment",
	}
	
def load_bill_text(bill, version):
	bt = BillType.by_value(bill.bill_type).xml_code
	bill_text_content = open("data/us/bills.text/%s/%s/%s%d%s.html" % (bill.congress, bt, bt, bill.number, version if version != None else "")).read()
	
	mods = lxml.etree.parse("data/us/bills.text/%s/%s/%s%d.mods.xml" % (bill.congress, bt, bt, bill.number))
	ns = { "mods": "http://www.loc.gov/mods/v3" }
	docdate = mods.xpath("string(mods:originInfo/mods:dateIssued)", namespaces=ns)
	gpo_url = mods.xpath("string(mods:identifier[@type='uri'])", namespaces=ns)
	gpo_pdf_url = mods.xpath("string(mods:location/url[@displayLabel='PDF rendition'])", namespaces=ns)
	doc_version = mods.xpath("string(mods:extension/mods:billVersion)", namespaces=ns)
	
	docdate = datetime.date(*(int(d) for d in docdate.split("-")))
	
	doc_version_name = bill_gpo_status_codes[doc_version]

	return {
		"text_html": bill_text_content,
		"docdate": docdate,
		"gpo_url": gpo_url,
		"gpo_pdf_url": gpo_pdf_url,
		"doc_version": doc_version,
		"doc_version_name": doc_version_name,
	}

def compare_xml_text(doc1, doc2):
    # Compare the text of two XML documents, marking up each document with new
    # <span> tags. The documents are modified in place.
    
    def make_bytes(s):
        if type(s) != str:
            s = s.encode("utf8")
        else:
            pass # assume already utf8
        return s
    
    def serialize_document(doc):
        from StringIO import StringIO
        class State(object):
            pass
        state = State()
        state.text = StringIO()
        state.offsets = list()
        state.charcount = 0
        def append_text(text, node, texttype, state):
            if not text: return
            text = make_bytes(text)
            state.text.write(text)
            state.offsets.append([state.charcount, len(text), node, texttype])
            state.charcount += len(text)
        def recurse_on(node, state):
            # etree handles text oddly: node.text contains the text of the element, but if
            # the element has children then only the text up to its first child, and node.tail
            # contains the text after the element but before the next sibling. To iterate the
            # text in document order, we cannot use node.iter().
            append_text(node.text, node, 0, state) # 0 == .text
            for child in node:
                recurse_on(child, state)
            append_text(node.tail, node, 1, state) # 1 == .tail
        recurse_on(doc.getroot(), state)
        state.text = state.text.getvalue()
        return state
        
    doc1data = serialize_document(doc1)
    doc2data = serialize_document(doc2)
    
    def reformat_diff(diff_iter):
        # Re-format the operations of the diffs to indicate the byte
        # offsets on the left and right.
        left_pos = 0
        right_pos = 0
        for op, length in diff_iter:
            left_len = length if op in ("-", "=") else 0
            right_len = length if op in ("+", "=") else 0
            yield (op, left_pos, left_len, right_pos, right_len)
            left_pos += left_len
            right_pos += right_len
           
    def slice_bytes(text, start, end):
        # Return the range [start:length] from the byte-representation of
        # the text string, returning unicode. If text is unicode, convert to
        # bytes, take the slice, and then convert back from UTF8 as best as
        # possible since we may have messed up the UTF8 encoding.
       return make_bytes(text)[start:end].decode("utf8", "replace")
           
    def mark_text(doc, offsets, pos, length, mode):
       # Wrap the text in doc at position pos and of byte length length
       # with a <span>, and set the class to mode.
       def make_wrapper(label=None):
           wrapper_node = lxml.etree.Element('span')
           wrapper_node.set('class', mode)
           if label: wrapper_node.set('make_wrapper_label', label)
           return wrapper_node
       for i, (off, offlen, offnode, offtype) in enumerate(offsets):
           # Does the change intersect this span?
           if pos >= off+offlen or pos+length <= off: continue
           
           if pos == off and length >= offlen:
               # The text to mark is the whole part of this span,
               # plus possibly some more.
               if offtype == 0:
                   # It is the node's .text, meaning replace the text
                   # that exists up to the node's first child.
                   w = make_wrapper("A")
                   w.text = offnode.text
                   offnode.text = ""
                   offnode.insert(0, w)
               else:
                   # It is the node's .tail, meaning replace the text
                   # that exists after the element and before the next
                   # sibling.
                   w = make_wrapper("B")
                   offtail = offnode.tail # see below
                   offnode.addnext(w)
                   w.text = offtail
                   w.tail = None
                   offnode.tail = ""
           elif pos == off and length < offlen:
               # The text to mark starts here but ends early.
               if offtype == 0:
                   w = make_wrapper("C")
                   offnode.insert(0, w)
                   w.text = slice_bytes(offnode.text, 0, length)
                   w.set("txt", slice_bytes(offnode.text, 0, length))
                   w.tail = slice_bytes(offnode.text, length, offlen)
                   offnode.text = ""
               else:
                   w = make_wrapper("D")
                   offtail = offnode.tail # get it early to avoid any automatic space normalization
                   offnode.addnext(w) # add it early for the same reason
                   w.text = slice_bytes(offtail, 0, length)
                   w.tail = slice_bytes(offtail, length, offlen)
                   offnode.tail = ""
               # After this point we may come back to edit more text in this
               # node after this point. However, what was in this node at offset
               # x is now in the tail of the new wrapper node at position x-length.
               offsets[i] = (off+length, offlen-length, w, 1)
           elif pos > off and pos+length >= off+offlen:
               # The text to mark starts part way into this span and ends
               # at the end (or beyond).
               if offtype == 0:
                   w = make_wrapper("E")
                   offnode.insert(0, w)
                   w.text = slice_bytes(offnode.text, pos-off, offlen)
                   offnode.text = slice_bytes(offnode.text, 0, pos-off)
               else:
                   w = make_wrapper("F")
                   offtail = offnode.tail # see above
                   offnode.addnext(w) # see above
                   w.text = slice_bytes(offtail, pos-off, offlen)
                   w.tail = None
                   offnode.tail = slice_bytes(offtail, 0, pos-off)
           elif pos > off and pos+length < off+offlen:
               # The text to mark starts part way into this span and ends
               # early.
               if offtype == 0:
                   w = make_wrapper("G")
                   offnode.insert(0, w)
                   w.text = slice_bytes(offnode.text, pos-off, (pos-off)+length)
                   w.tail = slice_bytes(offnode.text, (pos-off)+length, offlen)
                   offnode.text = slice_bytes(offnode.text, 0, pos-off)
               else:
                   if len(make_bytes(offnode.tail)) != offlen: raise Exception(str(len(make_bytes(offnode.tail))) + "/" + str(offlen) + "/" + lxml.etree.tostring(offnode))
                   w = make_wrapper("H")
                   offtail = offnode.tail # see above
                   offnode.addnext(w) # see above
                   w.text = slice_bytes(offtail, pos-off, (pos-off)+length)
                   w.tail = slice_bytes(offtail, (pos-off)+length, offlen)
                   offnode.tail = slice_bytes(offtail, 0, pos-off)
               # After this point we may come back to edit more text in this
               # node after this point. However, what was in this node at offset
               # x is now in the tail of the new wrapper node at position x-length.
               offsets[i] = (off+(pos-off)+length, offlen-(pos-off)-length, w, 1)
           else:
               raise Exception()
           
           if pos+length > off+offlen:
               d = off+offlen - pos
               pos += d
               length -= d
               if length <= 0: return
           
    def get_bounding_nodes(pos, length, offsets):
       nodes = []
       for off, offlen, offnode, offtype in offsets:
           if off <= pos < off+offlen:
               nodes.append(offnode)
           if off <= pos+length < off+offlen:
               nodes.append(offnode)
       if len(nodes) == 0: return None
       return nodes[0], nodes[-1]
    def mark_correspondence(leftnode, rightnode, idx, ab):
        if not leftnode.get("id"): leftnode.set("id", "left_%d%s" % (idx, ab))
        if not rightnode.get("id"): rightnode.set("id", "right_%d%s" % (idx, ab))
        leftnode.set("corresponds_with_" + ab, rightnode.get("id"))
        rightnode.set("corresponds_with_" + ab, leftnode.get("id"))
           
    import diff_match_patch
    diff = diff_match_patch.diff(doc1data.text, doc2data.text)
    idx = 0
    for op, left_pos, left_len, right_pos, right_len in reformat_diff(diff):
        idx += 1
        left_nodes = get_bounding_nodes(left_pos, left_len, doc1data.offsets)
        right_nodes = get_bounding_nodes(right_pos, right_len, doc2data.offsets)
        if left_nodes and right_nodes:
            mark_correspondence(left_nodes[0], right_nodes[0], idx, "top")
            mark_correspondence(left_nodes[1], right_nodes[1], idx, "bottom")
        
        if op == "=" and doc1data.text[left_pos:left_pos+left_len] == doc2data.text[right_pos:right_pos+right_len]: continue
        if left_len > 0: mark_text(doc1, doc1data.offsets, left_pos, left_len, "del" if right_len == 0 else "change")
        if right_len > 0: mark_text(doc2, doc2data.offsets, right_pos, right_len, "ins" if left_len == 0 else "change")
    
    return doc1, doc2
    
if __name__ == "__main__":
    doc1 = lxml.etree.parse("data/us/bills.text/112/h/h3606ih.html")
    doc2 = lxml.etree.parse("data/us/bills.text/112/h/h3606eh.html")
    compare_xml_text(doc1, doc2)
    print lxml.etree.tostring(doc2)
