Getting Started with the TOM Toolkit
------------------------------------

So you’ve decided to run a Target Observation Manager. This article will
help you get started.

The TOM Toolkit is a `Django <https://www.djangoproject.com/>`__
project. This means you’ll be running an application based on the Django
framework when you run a TOM. If you decide to customize your TOM,
you’ll be working in Django. You’ll likely need some basic understanding
of python and we recommend all users work their way through the `Django
tutorial <https://docs.djangoproject.com/en/2.1/contents/>`__ first
before starting with the TOM Toolkit. It doesn’t take long, and you most
likely won’t need to utilize any advanced features.

Ready to go? Let’s get started.

Prerequisites
~~~~~~~~~~~~~

The TOM toolkit requires Python >= 3.7

If you are using Python 3.6 and cannot upgrade to 3.7, install the
``dataclasses`` backport:

::

   pip install dataclasses

Installing the TOM Toolkit and Django
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, we recommend using a `virtual
environment <https://docs.python.org/3/tutorial/venv.html>`__ for your
project. This will keep your TOM python packages seperate from your
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

…and create a new project, just like in the tutorial:

::

   django-admin startproject mytom

You should now have a fully functional standard Django installation
inside the ``mytom`` folder, with the TOM dependencies installed as
well.

Getting started with the ``tom_setup`` script.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We need to add the ``tom_setup`` app to our project’s
``INSTALLED_APPS``. Locate the ``settings.py`` file inside your project
directory (usually in a subdirectory of the main folder,
i.e. mytom/mytom/settings.py) and edit it so that it looks like this:

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

Run the setup script
~~~~~~~~~~~~~~~~~~~~

The ``tom_setup`` app contains a script that will bootstrap a new TOM in
your current project. Run it:

::

   ./manage.py tom_setup

The install script will ask you a few questions and then install your
TOM.

Running the dev server
~~~~~~~~~~~~~~~~~~~~~~

Now that the toolkit is installed, you’re ready to try it out!

First, run the necessary migrations:

::

   ./manage.py migrate

Now, start the dev server:

::

   ./manage.py runserver

Your new TOM should now be running on http://127.0.0.1:8000!
