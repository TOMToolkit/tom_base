Testing TOMs
------------

As functionality is added to a TOM system it is highly beneficial to write
`unittests <https://docs.python.org/3/library/unittest.html>`__ for each
new function and module added.  This allows you to easily and repeatably
test that the function behaves as expected, and makes error diagnosis much faster.
Although it can seem like extra work, ultimately writing unittests will save
you time in the long run.  For more on why unittests are valuable,
`read this <https://docs.djangoproject.com/en/5.0/intro/tutorial05/>`__.

The TOM Toolkit provides a built-in framework for writing unittests,
including some TOM-specific factory functions that enable you to
generate examples of TOM database entries for testing.  This is, in turn,
built on top of `Django's unittest framework <https://docs.djangoproject.com/en/5.0/topics/testing/overview/>`__, inheriting a wealth of
functionality.  This allows test code to be written which acts on a
stand-alone test database, meaning that any input used for testing
doesn't interfere with an operational TOM database.

Code Structure and Running Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are two main options on where the test code lives in your TOM,
depending on how you want to run the tests.  Here we follow convention and refer to
the top-level directory of your TOM as the `project` and the subdirectory
for the TOM as the `application`.  Although they are often called the same
name, the distinction matters because TOMs can have multiple `applications`
within the same `project`.  The actual test code will be the same regardless
of which option you use - this is described in the next section.

Option 1: Use the built-in manage.py application to run the tests
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

With this option, test code is run using ``manage.py``, just like management
commands.  ``manage.py`` is designed to consider any file with a filename
prefixed by ``test_`` within the project directory and subdirectories as test code,
and it will find them automatically.

If you chose this option, then it's good practise to place test code in the subdirectory for
the application that they apply to, in a file called ``tests.py``.    The code structure for this option would be:

::

   mytom/
   ├── data/
   ├── db.sqlite3
   ├── manage.py
   ├── mytom/
   │   ├── __init__.py
   │   ├── settings.py
   │   ├── urls.py
   │   ├── wsgi.py
   │   └── tests.py
   ├── static.
   ├── templates/
   └── tmp/

This gives you quite fine-grained control when it comes to running the tests.  You can either run
all tests at once:

::

$ ./manage.py test

...run just the tests for a specific application...

::

$ ./manage.py test mytom.tests


...run a specific TestClass (more on these below) for a specific application ...

::

$ ./manage.py test mytom.tests.MyTestCase

...or run just a particular method of a single TestClass:

::

$ ./manage.py test mytom.test.MyTestClass.test_my_function

Option 2: Use a test runner
+++++++++++++++++++++++++++

A test runner script instead of ``manage.py`` can be useful because it
allows you to have more sophisticated control over settings that can be
used specifically for testing purposes, independently of the settings
used for the TOM in operation.  This is commonly used in applications that
are designed to be re-useable.  For more information,
see `Testing Reusable Applications.
<https://docs.djangoproject.com/en/5.0/topics/testing/advanced/#testing-reusable-applications>`_

With this option, it's good practise to place your unittest code in a
single subdirectory in the top-level directory of your TOM, normally
called ``tests/``, and add the test runner script in the project directory:

::

   mytom/
   ├── data/
   ├── db.sqlite3
   ├── manage.py
   ├── runtests.py
   ├── mytom/
   │   ├── __init__.py
   │   ├── settings.py
   │   ├── urls.py
   │   └── wsgi.py
   ├── static.
   ├── templates/
   ├── tmp/
   └── tests/
   │   │   ├── test_settings.py
   │   │   ├── tests.py

All files with test code within the ``tests/`` subdirectory should have
filenames prefixed with ``test_``.

In addition to the test functions, which are located in ``tests.py``, this
option requires two short files in addition:

.. code-block::

    test_settings.py:

    SECRET_KEY = "fake-key"
    INSTALLED_APPS = [
        'whitenoise.runserver_nostatic',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.sites',
        'django_extensions',
        'guardian',
        'tom_common',
        'django_comments',
        'bootstrap4',
        'crispy_bootstrap4',
        'crispy_forms',
        'django_filters',
        'django_gravatar',
        'rest_framework',
        'rest_framework.authtoken',
        'tom_targets',
        'tom_alerts',
        'tom_catalogs',
        'tom_observations',
        'tom_dataproducts',
        'mytom',
        'tests',
    ]

Note that you may need to extend the contents of the test_settings.py file,
often by adding the corresponding information from your TOM's main
``settings.py``, depending on the information required for your tests.

.. code-block::

    runtests.py:

    import os
    import sys
    import argparse
    import django
    from django.conf import settings
    from django.test.utils import get_runner

    def get_args():

        parser = argparse.ArgumentParser()
        parser.add_argument('module', help='name of module to test or all')
        options = parser.parse_args()

        return options

    if __name__ == "__main__":
        options = get_args()
        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.test_settings"
        django.setup()
        TestRunner = get_runner(settings)
        test_runner = TestRunner()
        if options.module == 'all':
            failures = test_runner.run_tests(["tests"])
        else:
            failures = test_runner.run_tests([options.module])
        sys.exit(bool(failures))

The test runner offers you similarly fine-grained control over whether to
run all of the tests in your application at once, or a single function,
using the following syntax:

::

$ python runtests.py tests
$ python runtests.py tests.test_mytom
$ python runtests.py tests.test_mytom.TestCase
$ python runtests.py tests.test_mytom.TestCase.test_my_function

Writing Unittests
~~~~~~~~~~~~~~~~~

Regardless of how they are run, the anatomy of a unittest will be the same.
Unittests are composed as `classes`, inheriting from Django's ``TestCase`` class.

.. code-block::

    tests/test_mytom.py:

    from django.test import TestCase

    class TestMyFunctions(TestCase):

Each test class needs to have a ``setUp`` method and at least one test
method to be valid.  As the name suggests, the ``setUp`` method
configures the parameters of the test, for instance establishing any
input data necessary for the test.  These data should then be stored as
attributes of the TestCase instance so that they are available when the
test is run.  As a simple example, suppose you have written a function in
your TOM that converts a star's RA, Dec to galactic coordinates called
``calc_gal_coords``.  This function is stored in the file ``myfunctions.py``.

::

   mytom/
   ├── data/
   ├── db.sqlite3
   ├── manage.py
   ├── mytom/
   │   ├── __init__.py
   │   ├── settings.py
   │   ├── urls.py
   │   ├── wsgi.py
   │   └── myfunctions.py
   │   └── tests.py
   ├── static.
   ├── templates/
   └── tmp/

In order to test this, we need to set up some input data in the form of
coordinates.  We could do this just by setting some input RA, Dec values
as purely numerical attributes.  However, bearing in
mind that the TOM stores this information as entry in its
database, a more realistic test would present that information in the
form of a :doc:`Target object <../targets/index>`.  The Toolkit includes a number of
``factory`` classes designed to make it easy to create realistic input
data for testing purposes.

.. code-block::

    tests/test_mytom.py:

    from django.test import TestCase
    from mytom.myfunctions import calc_gal_coords
    from tom_targets.tests.factories import SiderealTargetFactory

    class TestMyFunctions(TestCase):
        def setUp(self):
            self.target = SiderealTargetFactory.create()
            self.target.name = 'test_target'
            self.target.ra = 262.71041667
            self.target.dec = -28.50847222

A test method can now be added to complete the TestCase, which calls
the TOM's function with the test input and compares the results from
the function with the expected output using an ``assert``
statement.  Python includes ``assert`` natively, but you can also use
`Numpy's testing suite <https://numpy.org/doc/stable/reference/routines.testing.html>`__
or the methods inherited from the ``TestCase`` class.

.. code-block::

    tests/test_mytom.py:

    from django.test import TestCase
    from mytom.myfunctions import calc_gal_coords
    from tom_targets.tests.factories import SiderealTargetFactory

    class TestMyFunctions(TestCase):
        def setUp(self):
            self.target = SiderealTargetFactory.create()
            self.target.name = 'test_target'
            self.target.ra = 262.71041667
            self.target.dec = -28.50847222

        def test_calc_gal_coords(self):

            expected_l = 358.62948127
            expected_b = 2.96696435

            (test_l, test_b) = calc_gal_coords(self.target.ra,
                                                self.target.dec)
            self.assertEqual(test_l, expected_l)
            self.assertEqual(test_b, expected_b)

You can add as many additional test methods to a ``TestCase`` as you like.

TOM's Built-in Tests and Factory Functions
++++++++++++++++++++++++++++++++++++++++++

The Toolkit provides a number of factory functions to generate input
data to test various objects in a TOM system.  These can be found in the ``tests``
subdirectory of the core modules of the TOM Toolkit:

- Targets: `tom_base/tom_targets/tests/factories.py <https://github.com/TOMToolkit/tom_base/blob/dev/tom_targets/tests/factories.py>`__
- Observations: `tom_base/tom_observations/tests/factories.py <https://github.com/TOMToolkit/tom_base/blob/dev/tom_observations/tests/factories.py>`__

The ``tests`` subdirectories for the Toolkit's core modules are also a great
resource if you are looking for more complex examples of test code.