:orphan:

Manually Installing the TOM Toolkit and Django
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

    These instructions are only meant to be used if you have NOT run the `make-tom.sh` script.
    The following sections walk you through the installation process run by `make-tom.sh` for those
    who prefer to install their TOM manually.

If you prefer to build your system manually, here's how.

Firstly, the TOM toolkit requires you to have Python >= 3.7 installed
on your machine.

If you are using Python 3.6 and cannot upgrade to 3.7, install the
``dataclasses`` backport:

::

   pip install dataclasses

We recommend using a `virtual
environment <https://docs.python.org/3/tutorial/venv.html>`__ for your
project. This will keep your TOM python packages separate from your
system python packages.

::

   python3 -m venv tom_env/

Now that we have created the virtual environment, we can activate it:

::

   source tom_env/bin/activate

You should now see ``(tom_env)`` prepended to your terminal prompt.

Now, install the TOM Toolkit:

::

   pip install tomtoolkit

This will also resolve the dependencies you need for the libraries
used by the Toolkit.  With this complete, your virtual environment has
everything it needs, and we can start building the TOM system.

Create a TOM system
~~~~~~~~~~~~~~~~~~~
The Toolkit provides a special ``tom_setup`` application, which will build
a functional, out-of-the-box TOM system for you.  Since this app is itself
a Django app, we first need to create a basic Django project in which to
run it:

::

   django-admin startproject mytom

This creates a default Django project inside the ``mytom`` folder.  Inside
this folder, you'll find a ``settings.py`` file, which will provide the
central configuration for your TOM system (usually in a subdirectory of
the main folder, i.e. mytom/mytom/settings.py).

We need to add the ``tom_setup`` app to our project’s list of
``INSTALLED_APPS`` in the ``settings.py`` file. Edit the list of apps so
that it looks like this:

.. code:: python

   INSTALLED_APPS = [
       'django.contrib.admin',
       'django.contrib.auth',
       'django.contrib.contenttypes',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',
       'tom_setup',
   ]


Now you can run the ``tom_setup`` app.  It contains a script that will
bootstrap a new TOM in your current project. Run it like this:

::

   ./manage.py tom_setup

The install script will ask you a few questions and then install your
TOM.

The ``tom_setup`` app will install the full set of the Toolkit's core
modules as a suite of apps.  Each one of these comes with database
model tables, forms, and much more designed for various astronomical
functions.  The last step is to perform a ``migration``, which ensures
these changes are applied correctly to your new TOM's database:

::

   ./manage.py migrate

Once the migration is complete you are ready to :ref:`run your TOM in a dev
server <runserver>`.