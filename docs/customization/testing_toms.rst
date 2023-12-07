Testing TOMs
------------

As functionality is added to a TOM system it is highly beneficial to write
`unittests <https://docs.python.org/3/library/unittest.html>`__ for each
new function and module added.  This allows you to easily and repeatably
test that the function behaves as expected, and makes error diagnosis faster.

The TOM Toolkit provides a built-in framework for writing unittests,
including some TOM-specific factory functions that enable you to
generate examples of TOM database entries for testing.  This is, in turn,
built on top of `Django's unittest framework <https://docs.djangoproject.com/en/5.0/topics/testing/overview/>`__, inheriting a wealth of
functionality.  This allows test code to be written which acts on a
stand-alone test database, meaning that any input used for testing
doesn't interfere with an operational TOM database.

Code Structure
--------------

It's good practise to place your unittest code in a single subdirectory
in the top-level directory of your TOM, normally called ``tests/``:

::

   mytom/
   ├── data/
   ├── db.sqlite3
   ├── manage.py
   ├── mytom/
   │   ├── __init__.py
   │   ├── settings.py
   │   ├── urls.py
   │   └── wsgi.py
   ├── static.
   ├── templates/
   ├── tmp/
   └── tests/

All files within this subdirectory should have filenames prefixed with ``test_``.
While this convention isn't essential, following a predictable structure
makes it easier to understand for other developers, and enables you to
take advantage of a test runner script.

