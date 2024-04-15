Getting Started with the TOM Toolkit
------------------------------------

So you’ve decided to run a Target and Observation Manager system. This article will
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

Quickstart
~~~~~~~~~~
The easiest way to getting a TOM system up and running on a Linux or Mac
is to use our make-tom script.  If you would rather install the TOM
manually, you can follow the instructions in the :doc:`Manual Installation
Guide </introduction/manual_installation>`, but we recommend using the
script if you are new to the TOM Toolkit.

This script will create a virtual environment
and install a TOM system on your local machine.  Simply clone
`the make-tom repository <https://github.com/TOMToolkit/make-tom>`_:

::

  git clone https://github.com/TOMToolkit/make-tom.git
  cd make-tom

Ensure that the script is executable...

::

  chmod +x make-tom.sh

...and then run the script, giving a name for your TOM's code repository
as the first argument.  You can call this whatever you like:

::

  ./make-tom.sh my_tom

Your TOM should now be initialized, and you are ready to spin up a server.

.. _runserver:

Running the dev server
~~~~~~~~~~~~~~~~~~~~~~

Now that your TOM has been built you can run it immediately, directly on
your local machine, using the command ``runserver``:

::

   ./manage.py runserver

Now, if you open a web browser, you can navigate to the URL
`http://127.0.0.1:8000 <http://127.0.0.1:8000>`_ and you should see your
new TOM up and running!  Go ahead and login to explore what it can do.