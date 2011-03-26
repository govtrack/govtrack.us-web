"""
Function which computes Bill title.
"""
from django.conf import settings
import re


def ordinate(num):
    if num % 100 >= 11 and num % 100 <= 13:
        return "th"
    elif num % 10 == 1:
        return "st"
    elif num % 10 == 2:
        return "nd"
    elif num % 10 == 3:
        return "rd"
    else:
        return "th"


def get_bill_number(bill, prev_session=True):
    "Compute display form of bill number"

    ret = '%s %s' % (bill.bill_type.label, bill.number)
    if prev_session and bill.congress != settings.CURRENT_CONGRESS:
        ret += ' (%s%s)' % (bill.congress, ordinate(bill.congress))
    return ret


def get_bill_title(bill, titles, titletype):
    """
    Compute bill title.

    Args:
        bill: ``Bill`` instance
        titles: list of (type, as) values, extracted from the XML
        titletype: ???

    Look for the last "as" attribute, and use popular title if exists, else short title, else official title.
    """

    # Look for a popular or, failing that, a short title.
    if titletype == 'popular':
        types = ('popular', 'short')
    else:
        types = ('short', 'popular')

    title = find_title(titles, types)
    
    # If this is for the official title text but we didn't
    # find another title so we're going to use that
    # for the display title, then return nada so that we 
    # don't repeat ourselves.
    if titletype == 'official' and title is None:
        return None
    
    # Continue on to find the official title.
    # If this is for the official title text, ignore what we previously found.
    if title is None or titletype == 'official':
        title = find_title(titles, 'official')
    if title is None:
        for type_, as_, content in reversed(titles):
            if content:
                title = content
                break
    if title is None:
        title = "No Title"
    
    # replace apostrophes/quotes with curly ones
    title = re.sub(r"(\S)(''|\")", r"\1" + u"\N{RIGHT DOUBLE QUOTATION MARK}", title)
    title = re.sub(r"(\S)'", r"\1" + u"\N{RIGHT SINGLE QUOTATION MARK}", title)
    title = re.sub(r"(''|\")", u"\N{LEFT DOUBLE QUOTATION MARK}", title)
    title = re.sub(r"'", u"\N{LEFT SINGLE QUOTATION MARK}", title)
        
    if titletype == 'official':
        return title
    else:
        return '%s: %s' % (get_bill_number(bill), title)


def find_title(titles, types):
    """
    Find last unempty title with one of specified types.

    Args:
        titles: list of (type, as, content) tuples.
        types: ordered from most wanted to least wanted
    """
    
    for type_, as_, content in reversed(titles):
        for test_type in types:
            if type_ == test_type and content:
                return content
    return None
