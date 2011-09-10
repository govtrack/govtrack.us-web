Xapian-Haystack -- A backend for Django-Haystack
================================================

Overview
--------
xapian-haystack is a backend for use with the Django Haystack search API and the Xapian search engine.

* More information on Haystack can be found here: `haystacksearch.org <http://haystacksearch.org/>`_.
* More information on Xapian can be found here: `xapian.org <http://xapian.org>`_.

Requirements
------------

- Python 2.4 (May work with 2.3, but untested)
- Django 1.0.x
- Django-Haystack 1.1.X (If you wish to use django-haystack 1.0.X, please use xapian-haystack 1.0.X)
- Xapian 1.0.13+ (May work with earlier versions, but untested)
- mod_wsgi 1.3.X

Notes
-----

- Due to an issue with mod_python possibly causing deadlocks with Xapian (`issue #364 <http://trac.xapian.org/ticket/364>`_), when Python is not invoked through the "main interpreter", mod_python is not supported with xapian-haystack.  It may work, with some tweaking, but your mileage will vary.

- Because Xapian does not support simultaneous ``WritableDatabase`` connections, it is *strongly* recommended that users take care when using ``RealTimeSearchIndex``.  If there is a possibility of simultaneous write attempts on the database, keep in mind that they are likely to trigger multiple reindex attempts on the search index.  If this occurs an `DatabaseLockError` exception will be raised by Xapian.  To avoid this, either set ``WSGIDaemonProcess processes=1`` or use some other way of ensuring that there are not multiple attempts to write to the indexes.  Alternatively, use ``SearchIndex`` and a cronjob to reindex content at set time intervals (sample cronjob can be found `here <http://gist.github.com/216247>`_) or derive your own ``SearchIndex`` to implement some other form of keeping your indexes up to date.  A good alternative is to use a `QueuedSearchIndex <http://github.com/toastdriven/queued_search>`_.

Installation
------------

#. Copy or symlink ``xapian_backend.py`` into ``haystack/backends/`` or install it by running one of the following commands:

    ``python setup.py install``

    or

    ``pip install xapian-haystack``
    
    or

    ``easy_install xapian-haystack``

#. Add ``HAYSTACK_XAPIAN_PATH`` to ``settings.py``
#. Set ``HAYSTACK_SEARCH_ENGINE`` to ``xapian``

Testing
-------

The easiest way to test xapian-haystack is to symlink or copy the ``xapian_haystack/tests`` folder into the haystack/tests folder so that your source tree resembles this layout::

    django-haystack
        |
        +---haystack
        |       |
        |       +---backends
        |              |
        |              +---solr_backend.py
        |              +---whoosh_backend.py
        |              +---xapian_backend.py
        +---tests
                |
                +---core
                |    |
                |    +---[...]
                |
                +---[...]
                |
                +---xapian_tests
                |       |
                |       +---[...]
                |
                +---xapian_settings.py

Once this is done, the tests can be executed in a similar fashion as the rest of the Haystack test-suite::

    django-admin.py test xapian_tests --settings=xapian_settings


Source
------

The latest source code can always be found here: `github.com/notanumber/xapian-haystack <http://github.com/notanumber/xapian-haystack/>`_

Credits
-------

xapian-haystack is maintained by `David Sauve <mailto:dsauve@trapeze.com>`_, and is funded by `Trapeze <http://www.trapeze.com>`_.

License
-------

xapian-haystack is Copyright (c) 2009-2010 David Sauve, Trapeze. It is free software, and may be redistributed under the terms specified in the LICENSE file. 

Questions, Comments, Concerns:
------------------------------

Feel free to open an issue here: `github.com/notanumber/xapian-haystack/issues <http://github.com/notanumber/xapian-haystack/issues>`_
Alternatively, ask questions on the django-haystack `mailing list <http://groups.google.com/group/django-haystack/>`_ or `irc channel <irc://irc.freenode.net/haystack>`_.