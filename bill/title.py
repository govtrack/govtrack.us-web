"""
Function which computes Bill title.
"""
import re

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal

def get_bill_number(bill, show_congress_number="ARCHIVAL"):
    "Compute display form of bill number"
    
    if bill.congress <= 42:
        # This is an American Memory bill. It's number is stored.
        ret = bill.title.split(":")[0]
    else:
        from bill.models import BillType
        ret = '%s %s' % (BillType.by_value(bill.bill_type).label, bill.number)
    if (bill.congress != settings.CURRENT_CONGRESS and show_congress_number == "ARCHIVAL") or show_congress_number == "ALL":
        ret += ' (%s)' % ordinal(bill.congress)
    return ret


def get_primary_bill_title(bill, titles, with_number=True, override_number=None):
    """
    Calculate primary bill title.

    Args:
        bill: ``Bill`` instance
        titles: list of (type, as) values, extracted from the XML
    """

    type_, as_, title  = find_title(titles)
    if title:
        title = normalize_title(title)
    else:
        title = "No Title"
    if with_number:
        return '%s: %s' % (get_bill_number(bill) if not override_number else override_number, title)
    else:
        return title


def get_secondary_bill_title(bill, titles):
    """
    Calculate secondary bill title.

    Return None if calcualated title is the same as primary title.
    """

    type_, as_, primary_title  = find_title(titles)
    type_, as_, official_title = find_title(titles, limit_type='official')
    if primary_title == official_title:
        return None
    else:
        return official_title



def normalize_title(title):
    "replace apostrophes/quotes with curly ones"

    title = re.sub(r"(\S)(''|\")", r"\1" + u"\N{RIGHT DOUBLE QUOTATION MARK}", title)
    title = re.sub(r"(\S)'", r"\1" + u"\N{RIGHT SINGLE QUOTATION MARK}", title)
    title = re.sub(r"(''|\")", u"\N{LEFT DOUBLE QUOTATION MARK}", title)
    title = re.sub(r"'", u"\N{LEFT SINGLE QUOTATION MARK}", title)
    return title


def find_title(titles, limit_type=None):
    """
    Find last unempty title with one of specified types.

    Args:
        titles: list of (type, as, content) tuples.
        limit_type: search only among titles of given type

    Some comments from Josh:

    There are three types of titles: official, short, and popular. The primary display title of a bill is a short title, falling back on a popular title if there are no short titles, and finally falling back on an official title if there are no other title types. To find the title of a given type, you take the *first* title that has the *last* as attribute, i.e. take the one marked:

     ... as="1" ...
     ... as="1" ...
     ... as="2" ... <-- use this one
     ... as="2" ...

    This is because the "as" attributes are given in chronological order, but within each "as" the first one is the most relevant (other titles can be for subparts of bills).
    """
   
    if limit_type:
        types = (limit_type,)
    else:
        types = ('short', 'popular', 'official')

    def weight(type_):
        try:
            return types.index(type_)
        except IndexError:
            return 100

    choice = None

    for type_, as_, content in titles:
        for test_type in types:
            if type_ == test_type and content:
                # If no title found before or
                # Founded title has different "as"
                # Then use the current title
                if (choice is None or
                    choice[0] == type_ and choice[1] != as_ or
                    weight(type_) < weight(choice[0])):
                    choice = (type_, as_, content)
    return choice if choice else (None, None, None)
