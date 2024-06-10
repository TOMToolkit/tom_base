General Deployment Tips
-----------------------

When it comes to deploying your tom for general use, there are a few
things you might want to consider.

Choosing a database
~~~~~~~~~~~~~~~~~~~

By default Django (and thus TOMs) use Sqlite as their database backend.
Sqlite is sufficient for the majority of use cases and can scale up to
the millions if not billions of rows, as long as you have the disk
space.

The one place where Sqlite falls behind other databases is it’s
performance under heavy concurrent writes. So if you are writing a TOM
that, for example, listens to the ZTF, LSST, and SCOUT alert streams and
creates targets from each alert you might want to look into Postgresql
or MySQL.

.. note::
    If you are using a database other than Sqlite, you will need to
    install the appropriate database driver in your virtual environment. For example,
    if you are using Postgresql you will need to install the `psycopg2-binary` package.

Set your TOM’s hostname in the default site
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In your TOM’s admin area (/admin/) on your production TOM you will
notice a section called “Sites.” There should be one site object, you
should edit it so that its hostname is accurate for production. Some
functionalities of the TOM rely on this value to properly set up
redirects, etc.

Basic security
~~~~~~~~~~~~~~

If you are exposing your TOM to the internet you should make sure that
basic security precautions have been taken. Make sure that any views
which expose sensitive data, perform any kind of modification to the
database or cause large amounts of server load are properly protected
and require authentication.

If you plan on making your TOM open source, take care not to check in
any secrets, passwords, or credentials. This includes database settings,
API keys, or a multitude of other things that you wouldn’t want to throw
out on the internet for everyone to see. Note that if you are using git,
removing a secret from a file and then committing it **does not remove
the secret** it will still exist in the repo’s history and be trivially
accessible. You will need to clean your repo’s history if you commit and
sensitive data.

Enforce basic password requirements (TOMs by default will do this) and
encourage your users to exercise basic security measures, like using a
password manager and not reusing passwords.

robots.txt
~~~~~~~~~~
As of version 2.17, TOM Toolkit serves a default ``robots.txt`` file
that disallows all (well-behaved) web crawlers. Point a browser to the
``/robots.txt`` endpoint of your TOM to see it. If you want to change that
behavior, you can supply the path to a custom ``robots.txt`` file in the
``settings.py`` file:

.. code:: python

    ROBOTS_TXT_PATH = '/path/to/your/robots.txt'


If you provide the path to a file that does not exist, TOM Toolkit will still
serve the default ``robots.txt`` file and log a warning message to that effect.

Additional background on the ``robots.txt`` file can be found
`here <https://en.wikipedia.org/wiki/Robots_exclusion_standard>`_.