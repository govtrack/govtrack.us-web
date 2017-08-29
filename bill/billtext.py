if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, ".")
    sys.path.insert(0, "lib")

import datetime, lxml, os.path, re
from bill.status import BillStatus

bill_gpo_status_codes = {
    "ah": ("Amendment", None),
    "ah2": ("Amendment", None),
    "as": ("Amendment", None),
    "as2": ("Amendment", None),
    "ash": ("Additional Sponsors", None),
    "sas": ("Additional Sponsors", None),
    "sc": ("Sponsor Change", None),
    "ath": ("Resolution Agreed to by House", { BillStatus.passed_simpleres, BillStatus.passed_concurrentres, BillStatus.pass_over_house }),
    "ats": ("Resolution Agreed to by Senate", { BillStatus.passed_simpleres, BillStatus.passed_concurrentres, BillStatus.pass_over_senate }),
    "cdh": ("Committee Discharged", None),
    "cds": ("Committee Discharged", None),
    "cph": ("Considered and Passed by the House", { BillStatus.pass_over_house }),
    "cps": ("Considered and Passed by the Senate", { BillStatus.pass_over_senate }),
    "eah": ("Passed the House (Engrossed) with an Amendment", { BillStatus.pass_back_house }),
    "eas": ("Passed the Senate (Engrossed) with an Amendment", { BillStatus.pass_back_senate }),
    "eh": ("Passed the House (Engrossed)", { BillStatus.pass_over_house }),
    "ehr": ("Passed the House (Engrossed)/Reprint", None),
    "eh_s": ("Passed the House (Engrossed)/Star Print", None),
    "enr": ("Passed Congress/Enrolled Bill", { BillStatus.passed_bill }),
    "renr": ("Passed Congress/Re-enrolled", None),
    "es": ("Passed the Senate (Engrossed)", { BillStatus.pass_over_senate }),
    "esr": ("Passed the Senate (Engrossed)/Reprint", None),
    "es_s": ("Passed the Senate (Engrossed)/Star Print", None),
    "fah": ("Failed Amendment", None),
    "hdh": ("Held at Desk in the House", None),
    "hds": ("Held at Desk in the Senate", None),
    "ih": ("Introduced", { BillStatus.introduced }),
    "ihr": ("Introduced/Reprint", None),
    "ih_s": ("Introduced/Star Print", None),
    "is": ("Introduced", { BillStatus.introduced }),
    "isr": ("Introduced/Reprint", None),
    "is_s": ("Introduced/Star Print", None),
    "iph": ("Indefinitely Postponed in the House", None),
    "ips": ("Indefinitely Postponed in the Senate", None),
    "lth": ("Laid on Table in the House", None),
    "lts": ("Laid on Table in the Senate", None),
    "oph": ("Ordered to be Printed", None),
    "ops": ("Ordered to be Printed", None),
    "pch": ("Placed on Calendar in the House", None),
    "pcs": ("Placed on Calendar in the Senate", None),
    "pp": ("Public Print", None),
    "pap": ("Printed as Passed", None),
    "rah": ("Referred to House Committee (w/ Amendments)", { BillStatus.introduced }),
    "ras": ("Referred to Senate Committee (w/ Amendments)", { BillStatus.introduced }),
    "rch": ("Reference Change", None),
    "rcs": ("Reference Change", None),
    "rdh": ("Received by the House", None),
    "rds": ("Received by the Senate", None),
    "reah": ("Passed the House (Re-Engrossed) with an Amendment", None),
    "re": ("Reprint of an Amendment", None),
    "res": ("Passed the Senate (Re-Engrossed) with an Amendment", None),
    "rfh": ("Referred to House Committee", None), # second chamber
    "rfhr": ("Referred to House Committee/Reprint", None),
    "rfh_s": ("Referred to House Committee/Star Print", None),
    "rfs": ("Referred to Senate Committee", None), # second chamber
    "rfsr": ("Referred to Senate Committee/Reprint", None),
    "rfs_s": ("Referred to Senate Committee/Star Print", None),
    "rh": ("Reported by House Committee", { BillStatus.reported }),
    "rhr": ("Reported by House Committee/Reprint", None),
    "rh_s": ("Reported by House Committee/Star Print", None),
    "rs": ("Reported by Senate Committee", { BillStatus.reported }),
    "rsr": ("Reported by Senate Committee/Reprint", None),
    "rs_s": ("Reported by Senate Committee/Star Print", None),
    "rih": ("Referral Instructions in the House", None),
    "ris": ("Referral Instructions in the Senate", None),
    "rth": ("Referred to House Committee", { BillStatus.introduced }), # originating chamber
    "rts": ("Referred to Senate Committee", { BillStatus.introduced }), # originating chamber
    "s_p": ("Star Print of an Amendment", None),
    "fph": ("Failed Passage in the House", None),
    "fps": ("Failed Passage in the Senate", None),
    }

def get_gpo_status_code_name(doc_version):
    # handle e.g. "eas2"
    digit_suffix = ""
    while len(doc_version) > 0 and doc_version[-1].isdigit():
        digit_suffix = doc_version[-1] + digit_suffix
        doc_version = doc_version[:-1]
    
    doc_version_name = bill_gpo_status_codes.get(doc_version, ("Unknown Status (%s)" % doc_version, None))[0]

    if digit_suffix: doc_version_name += " " + digit_suffix

    return doc_version_name

def get_gpo_status_code_corresponding_status(doc_version):
    ret = bill_gpo_status_codes.get(doc_version, (None, None))[1]
    if ret is None: ret = set()
    return ret

def get_current_version(bill):
    return load_bill_text(bill, None, mods_only=True)["doc_version"]
    
def load_bill_mods_metadata(fn):
    mods = lxml.etree.parse(fn)
    ns = { "mods": "http://www.loc.gov/mods/v3" }
    
    docdate = mods.xpath("string(mods:originInfo/mods:dateIssued)", namespaces=ns)
    gpo_url = "http://www.gpo.gov/fdsys/search/pagedetails.action?packageId=" + mods.xpath("string(mods:recordInfo/mods:recordIdentifier[@source='DGPO'])", namespaces=ns)
    #gpo_url = mods.xpath("string(mods:identifier[@type='uri'])", namespaces=ns)
    gpo_pdf_url = mods.xpath("string(mods:location/mods:url[@displayLabel='PDF rendition'])", namespaces=ns)
    doc_version = mods.xpath("string(mods:extension/mods:billVersion)", namespaces=ns)
    numpages = mods.xpath("string(mods:physicalDescription/mods:extent)", namespaces=ns)
    if numpages: numpages = re.sub(r" p\.$", " pages", numpages)
    
    docdate = datetime.date(*(int(d) for d in docdate.split("-")))
    doc_version_name = get_gpo_status_code_name(doc_version)

    # load a list of citations as marked up by GPO
    citations = []
    for cite in mods.xpath("//mods:identifier", namespaces=ns):
        if cite.get("type") == "USC citation":
            citations.append( parse_usc_citation(cite) )
        elif cite.get("type") == "Statute citation":
            citations.append({ "type": "statutes_at_large", "text": cite.text })
        elif cite.get("type") == "public law citation":
            try:
                congress_cite, slip_law_num = re.match(r"Public Law (\d+)-(\d+)$", cite.text).groups()
                citations.append({ "type": "slip_law", "text": cite.text, "congress": int(congress_cite), "number": int(slip_law_num) })
            except:
                citations.append({ "type": "unknown", "text": cite.text })
            
    return {
        "docdate": docdate,
        "gpo_url": gpo_url,
        "gpo_pdf_url": gpo_pdf_url,
        "doc_version": doc_version,
        "doc_version_name": doc_version_name,
        "numpages": numpages,
        "citations": citations,
    }

def parse_usc_citation(cite):
    m = re.match(r"(\d+)\s*U.S.C.(\s*App.)?\s*Chapter\s*(\S+)$", cite.text)
    if m:
        title_cite, title_app_cite, chapter_cite = m.groups()
        if title_app_cite: title_cite += "a"
        return { "type": "usc-chapter", "text": cite.text, "title": title_cite, "chapter": chapter_cite, "key" : "usc/chapter/" + title_cite + "/" + chapter_cite }
    
    m = re.match(r"(\d+\S*)\s*U.S.C.(\s*App.)?\s*([^\s(]+?)?\s*(\(.*|et ?seq\.?|note)?$", cite.text)
    if m:
        title_cite, title_app_cite, sec_cite, para_cite = m.groups()
        if title_app_cite: title_cite += "a"
        if para_cite and para_cite.strip() == "": para_cite = None
        
        # The citation may contain any number of dashes. At most one may indicate
        # a range, and the rest are dashes that appear within section numbers themselves.
        # Loop through all of the dashes and check if it splits the citation into two
        # valid section numbers (i.e. actually appears in the USC) that are also near
        # each other (same parent).
        #
        # A nice example is 16 U.S.C. 3839aa-8, where both "3839aa" and "8" are valid
        # sections but are far apart, so this does not indicate a range.
        #
        # Skip this if there is a paragraph in the citation --- that can't be appended
        # to a range.
        sec_dash_parts = sec_cite.split("-") if not para_cite else []
        for i in xrange(1, len(sec_dash_parts)):
            # Split the citation around the dash to check each half.
            sec_parts = ["-".join(sec_dash_parts[:i]),
                         "-".join(sec_dash_parts[i:])]
            from models import USCSection
            matched_secs = list(USCSection.objects.filter(citation__in = 
                [("usc/" + title_cite + "/" + sec_part) for sec_part in sec_parts]))
            if len(matched_secs) != 2: continue # one or the other was not a valid section number
            if matched_secs[0].parent_section_id != matched_secs[1].parent_section_id: continue # not nearby
            return { "type": "usc", "text": cite.text, "title": title_cite, "section": sec_parts[0], "paragraph": None, "range_to_section": sec_parts[1], "key" : "usc/" + title_cite + "/" + sec_parts[0] }
            
        # Not a range.
        return { "type": "usc-section", "text": cite.text, "title": title_cite, "section": sec_cite, "paragraph" : para_cite, "key" : "usc/" + title_cite + "/" + sec_cite }
        
    return { "type": "unknown", "text": cite.text }

def get_bill_text_versions(bill):
    from os import listdir
    d = bill.data_dir_path + "/text-versions"
    if not os.path.exists(d):
        return # don't yield anything, no text available
    for st in listdir(d):
        fn = bill.data_dir_path + "/text-versions/" + st + "/data.json"
        if os.path.exists(fn):
            yield st

def get_bill_text_metadata(bill, version):
    from bill.models import BillType # has to be here and not module-level to avoid cyclic dependency
    import glob, json

    bt = BillType.by_value(bill.bill_type).slug
    basename = "data/congress/%d/bills/%s/%s%d/text-versions" % (bill.congress, bt, bt, bill.number)
    
    if version == None:
        # Cycle through files to find most recent version by date.
        dat = None
        for versionfile in glob.glob(basename + "/*/data.json"):
            d = json.load(open(versionfile))
            if not dat or d["issued_on"] > dat["issued_on"]:
                dat = d
        if not dat: return None
    else:
        dat = json.load(open(basename + "/%s/data.json" % version))

    # human readable status name

    dat["status_name"] = get_gpo_status_code_name(dat["version_code"])
    dat["corresponding_status_codes"] = get_gpo_status_code_corresponding_status(dat["version_code"])

    # parse date

    dat["issued_on"] = datetime.date(*(int(d) for d in dat["issued_on"].split("-")))

    # find content files
        
    basename += "/" + dat["version_code"]

    bt2 = BillType.by_value(bill.bill_type).xml_code
    html_fn = "data/congress-bill-text-legacy/%s/%s/%s%d%s.html" % (bill.congress, bt2, bt2, bill.number, dat["version_code"])

    if os.path.exists(basename + "/mods.xml"):
        dat["mods_file"] = basename + "/mods.xml"

    # get a plain text file if one exists
    if os.path.exists(basename + "/document.txt"):
        dat["text_file"] = basename + "/document.txt"
        dat["has_displayable_text"] = True

        for source in dat.get("sources", []):
            if source["source"] == "statutes":
                dat["text_file_source"] = "statutes"

    # get an HTML file if one exists
    if os.path.exists(html_fn):
        dat["html_file"] = html_fn
        dat["has_displayable_text"] = True

    # get a PDF file if one exists
    pdf_fn = "../scripts/congress-pdf-config/" + basename.replace("data/congress", "data") + "/document.pdf"
    if os.path.exists(pdf_fn):
        dat["pdf_file"] = pdf_fn
        dat["has_thumbnail"] = True
        dat["thumbnail_path"] = bill.get_absolute_url() + "/_text_image"

    # get an XML file if one exists
    if os.path.exists(basename + "/catoxml.xml"):
        dat["xml_file"] = basename + "/catoxml.xml"
        dat["has_displayable_text"] = True
        dat["xml_file_source"] = "cato-deepbills"
    elif os.path.exists(basename + "/document.xml"):
        dat["xml_file"] = basename + "/document.xml"
        dat["has_displayable_text"] = True

    return dat
        
def load_bill_text(bill, version, plain_text=False, mods_only=False, with_citations=False):
    # Load bill text info from the Congress project data directory.
    # We have JSON files for metadata and plain text files mirrored from GPO
    # containing bill text (either from the Statutes at Large OCR'ed text
    # layers, or from GPO FDSys's BILLS collection).
    
    dat = get_bill_text_metadata(bill, version)
    if not dat:
        # No text is available.
        if plain_text:
            return "" # for indexing, just return empty string if no text is available
        raise IOError("Bill text is not available for this bill.")

    ret = {
        "bill_id": bill.id,
        "bill_name": bill.title,
        "has_displayable_text": dat.get("has_displayable_text"),
    }

    # Load basic metadata from a MODS file if one exists.
    if "mods_file" in dat:
        ret.update(load_bill_mods_metadata(dat["mods_file"]))

    # Otherwise fall back on using the text-versions data.json file. We may have
    # this for historical bills that we don't have a MODS file for.
    else:
        gpo_url = dat["urls"]["pdf"]

        m = re.match(r"http://www.gpo.gov/fdsys/pkg/(STATUTE-\d+)/pdf/(STATUTE-\d+-.*).pdf", gpo_url)
        if m:
            # TODO (but not needed right now): Docs from the BILLS collection.
            gpo_url = "http://www.gpo.gov/fdsys/granule/%s/%s/content-detail.html" % m.groups()

        ret.update({
            "docdate": dat["issued_on"],
            "gpo_url": gpo_url,
            "gpo_pdf_url": dat["urls"]["pdf"],
            "doc_version": dat["version_code"],
            "doc_version_name": get_gpo_status_code_name(dat["version_code"]),
        })

    # Pass through some fields.
    for f in ('html_file', 'xml_file', 'pdf_file', 'has_thumbnail', 'thumbnail_path'):
        if f in dat:
            ret[f] = dat[f]

    if with_citations: #and and not settings.DEBUG:
        load_citation_info(ret)

    # If the caller only wants metadata, return it.
    if mods_only:
        return ret

    if "xml_file" in dat and not plain_text:
        # convert XML on the fly to HTML
        import lxml.html, congressxml
        ret.update({
            "text_html": lxml.html.tostring(congressxml.convert_xml(dat["xml_file"])),
            "source": dat.get("xml_file_source"),
        })

    elif "html_file" in dat and not plain_text:
        # This will be for bills around the 103rd-108th Congresses when
        # bill text is available from GPO but not in XML.
        ret.update({
            "text_html": open(dat["html_file"]).read().decode("utf8"),
        })

    elif "text_file" in dat:
        # bill text from the Statutes at Large, or when plain_text is True then from GPO

        bill_text_content = open(dat["text_file"]).read().decode("utf8")

        # In the GPO BILLS collection, there's gunk at the top and bottom that we'd
        # rather just remove: metadata in brackets at the top, and <all> at the end.
        # We remove it because it's not really useful when indexing.
        if bill_text_content:
            bill_text_content = re.sub(r"^\s*(\[[^\n]+\]\s*)*", "", bill_text_content)
            bill_text_content = re.sub(r"\s*<all>\s*$", "", bill_text_content)

        # Caller just wants the plain text?
        if plain_text:
            # replace form feeds (OCR'd layers only) with an indication of the page break
            return bill_text_content.replace(u"\u000C", "\n=============================================\n")
            
        # Return the text wrapped in <pre>, and replace form feeds with an <hr>.
        import cgi
        bill_text_content = "<pre>" + cgi.escape(bill_text_content) + "</pre>"
        bill_text_content = bill_text_content.replace(u"\u000C", "<hr>") # (OCR'd layers only)

        ret.update({
            "text_html": bill_text_content,
            "source": dat.get("text_file_source"),
        })

    return ret

def load_citation_info(metadata):
    if "citations" not in metadata: return

    from models import USCSection
    from search import parse_slip_law_number
    import re

    # gather the citations listed in the MODS file

    slip_laws = []
    statutes = []
    usc_sections = []
    other = []

    usc_other = USCSection(id="_make_this_instance_hashable", name="Other Citations", ordering=99999)

    for cite in metadata["citations"]:
        if cite["type"] == "slip_law":
            slip_laws.append(cite)
            cite["bill"] = parse_slip_law_number(cite["text"])
        elif cite["type"] == "statutes_at_large":
            statutes.append(cite)
        elif cite["type"] in ("usc-section", "usc-chapter"):
            # Build a tree of title-chapter-...-section nodes so we can
            # display the citations in context.
            try:
                sec_obj = USCSection.objects.get(citation=cite["key"])
            except: # USCSection.DoesNotExist and MultipleObjectsReturned both possible
                # create a fake entry for the sake of output
                # the 'id' field is set to make these objects properly hashable
                sec_obj = USCSection(id=cite["text"], name=cite["text"], parent_section=usc_other)

            if "range_to_section" in cite:
                sec_obj.range_to_section = cite["range_to_section"]

            sec_obj.link = sec_obj.get_cornell_lii_link(cite.get("paragraph"))

            usc_sections.append(sec_obj)
        else:
            other.append(cite)

    # sort slip laws
    slip_laws.sort(key = lambda x : (x["congress"], x["number"]))

    # build a tree for USC citations

    usc = { }
    for sec_obj in usc_sections:
            # recursively go up to the title to find the path from title to this section
            path = [sec_obj]
            so = sec_obj
            while so.parent_section:
                so = so.parent_section
                so.link = so.get_cornell_lii_link()
                path.append(so)

            # now create a tree from the path
            container = usc
            for p in reversed(path):
                container["_count"] = container.get("_count", 0) + 1
                if p not in container: container[p] = { }
                container = container[p]

    # restructure the tree into a flattened list with indentation attributes on each row
    def ucfirst(s): return s[0].upper() + s[1:]
    def rebuild_usc_sec(seclist, indent=0):
        ret = []
        seclist = [kv for kv in seclist.items() if kv[0] != "_count"]
        seclist = sorted(seclist, key=lambda x : x[0].ordering)
        for sec, subparts in seclist:
            ret.append({
                "text": (ucfirst(sec.level_type + ((" " + sec.number) if sec.number else "") + (": " if sec.name else "")) if sec.level_type else "") + (sec.name_recased if sec.name else ""),
                "link": getattr(sec, "link", None),
                "range_to_section": getattr(sec, "range_to_section", None),
                "indent": indent,
            })
            ret.extend(rebuild_usc_sec(subparts, indent=indent+1))
        return ret
    usc = rebuild_usc_sec(usc)

    metadata["citations"] = {
        "slip_laws": slip_laws,
        "statutes": statutes,
        "usc": usc,
        "other": other,
        "count": len(slip_laws)+len(statutes)+len(usc)+len(other)
    }

    
if __name__ == "__main__":
    import pprint
    pprint.pprint(bill_gpo_status_codes)
