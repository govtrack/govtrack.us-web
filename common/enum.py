# -*- coding: utf-8 -*-
"""
This module provides ``Enum`` class which simplifies work with enumerated list of choices.
This implementation is specially developed for use in django models.

Example of usage::

    from common import enum

    class Color(enum.Enum):
        red = enum.Item(1)
        green = enum.Item(2, 'So greeeen')


We defined here two items. They are accessable as ``Color.red`` and ``Color.green``.
``Color.red`` will give you ``1``. So ``Color.red == 1`` is ``True``.

First item (``Color.red``) has the label same to its key i.e., "red". Second item (``Color.green``) has the custom label.  Labels are used when Color object are queried for the (key, label) pairs. This happens, for example, when we use Color object as the value for the ``choices`` argument of django field::

    class Fruit(models.Model):
        color = models.IntegerField(choices=Color, default=Color.red)

We can use Color object as ``choices`` argument because ``enum.Enum`` class provides custom __iter__
method which returs (key, label) pairs.

Also keep in mind that ``Color.red`` is not simple integer. It is like integer but has
some extra methods. Look example:

    Color.green == 2
    Color.green.label == "So greeeen"
    Color.green.key == "green"

Other useful methods of enum.Enum class::

   Color.by_value(1) == Color.red
   Color.by_key("red") == Color.red
   Color.values == [Color.red, Color.green]
   Color.random_value() == "Random value choosed from Color items"

Some tests:

# Common usage of enum module
>>> class Body(Enum):
...     sedan = Item(1, u'Sedan')
...     hatchback = Item(2, u'Hatchback')
>>> set(Body)
set([(1, u'Sedan'), (2, u'Hatchback')])
>>> Body.sedan
1

# Build Enum class from list of tuples
>>> Body = build(((1, u'Sedan'), (2, u'Hatchback')))
>>> set(Body)
set([(1, u'Sedan'), (2, u'Hatchback')])

# Specify items with ``_choices`` attribute
>>> class Body(Enum):
...     _choices = ((1, u'Sedan'), (2, u'Hatchback'))
>>> set(Body)
set([(1, u'Sedan'), (2, u'Hatchback')])

# ``_choices`` also could be a dict instance
>>> class Body(Enum):
...     _choices = dict(Sedan=1, Hatchback=2)
>>> set(Body)
set([(1, 'Sedan'), (2, 'Hatchback')])

# Get enum Item by its value
>>> Body.by_value(1).key
'Sedan'

# Pass arbitrary data to items
>>> class Color(Enum):
...     red = Item(1, 'Red', example='Apple')
...     green = Item(2, 'Green', example='Tree')
>>> Color.green.example
'Tree'
"""

import re
from random import choice

class NotFound(Exception):
    "Raise when could not found item with specified parameters"

def setup_item(obj, value, label, **kwargs):
    obj.value = value
    if label is None:
        obj.label = str(obj)
    else:
        obj.label = label
    for ikey, ivalue in kwargs.items():
        setattr(obj, ikey, ivalue)
    return obj


class IntItem(int):
    def __new__(cls, value, label=None, **kwargs):
        obj =  int.__new__(cls, value)
        return setup_item(obj, value, label, **kwargs)


class StrItem(str):
    def __new__(cls, value, label=None, **kwargs):
        obj =  str.__new__(cls, value)
        return setup_item(obj, value, label, **kwargs)


def Item(value, *args, **kwargs):
    if isinstance(value, int):
        return IntItem(value, *args, **kwargs)
    else:
        return StrItem(value, *args, **kwargs)


def items_from_choices(choices):
    """
    Create dict of enum.Item objects from given values.
    Args:
        choices: dict (key->value) or list of pairs [(value, key), ...]
    """

    items = {}
    if isinstance(choices, dict):
        choices = [(y, x) for x, y in choices.items()]
    for value, label in choices:
        key = label.replace(' ', '_').replace('-', '_')
        key = re.sub(r'_+', '_', key)
        rex = re.compile(r'^[a-z0-9_]*$', re.I)
        if not rex.match(key):
            raise Exception('Could not create key from label: %s' % label)
        items[key] = Item(value, label)
    return items


class MetaEnum(type):
    """
    Find all enum.Item attributes and save them into ``_items`` attribute.
    """

    def __new__(cls, name, bases, attrs):
        items = {}
        for base in bases:
            if isinstance(base, MetaEnum):
                items.update(base._items)
        if '_choices' in attrs:
            attrs.update(items_from_choices(attrs['_choices']))
            del attrs['_choices']
        for key, attr in list(attrs.items()):
            if isinstance(attr, (IntItem, StrItem)):
                attr.key = key
                items[key] = attr
                del attrs[key]
        attrs['_items'] = items
        return type.__new__(cls, name, bases, attrs)

    """
    Public methods:
    """

    def __iter__(cls):
        """
        Iterate over tuples of (value, label)
        """

        return iter(cls.choices())

    def __len__(self):
        """
        Return the number of enum.Item objects.
        """

        return len(self._items)

    def choices(cls):
        """
        Return tuples of (value, label) for all enum.Item objects.
        """

        return [(x.value, x.label) for x in cls._items.values()]

    def values(self):
        """
        Return list of values of all enum.Item objects.
        """

        return list(self._items.values())

    def random_value(cls):
        """
        Return random value of enum.Item object.
        """

        return choice(list(cls._items.values()))

    """
    Private methods:
    """

    def __getattribute__(self, key):
        """
        Each enum.Item object could be accessed as enum.Enum instance's attribute.
        """

        items = type.__getattribute__(self, '_items')
        if key in items:
            return items[key]
        else:
            if key.startswith('by_'):
                return type.__getattribute__(self, '_by_attribute')(key[3:])
            else:
                return type.__getattribute__(self, key)

    def _by_attribute(cls, attr):
        def func(value):
            """
            Return enum.Item which has attribute with specified value.
            """
            for x in cls._items.values():
                if getattr(x, attr) == value:
                    return x
            raise NotFound('Could not found item which %s attribute is %s' % (attr, value))
        return func

    def by_key(cls, key):
        """
        Return enum.Item which has the given key.
        """

        return cls._items[key]



class Enum(object, metaclass=MetaEnum):
    NotFound = NotFound


def build(choices):
    class _Enum(Enum):
        _choices = choices
    return _Enum


if __name__ == '__main__':
    import doctest
    doctest.testmod()
