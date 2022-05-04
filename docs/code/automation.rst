Automating tasks for your TOM
-----------------------------

Your TOM may have a need to run a task on a regular schedule without
human intervention. With the help of a built-in Django feature and cron,
this can be accomplished. Perhaps you want to check for and download
data from your scheduled observations every hour, or see if any brokers
have published new candidates that meet the criteria of a previous
search–all that would be required is a bit of code to call those
built-in functions, and a crontab update.

Create a management command
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django provides the ability to register actions using `management
commands <https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/>`__.
These actions can then be called from the command line.

Starting a new django “app”
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Django recommends creating separate “apps” to contain your management
commands (among other things, like custom models and views) so we’ll
start with creating a new app called “myapp”. You can read more about
Django reusable apps `in the official
documentation <https://docs.djangoproject.com/en/2.2/intro/tutorial01/#creating-the-polls-app>`__.

::

   ./manage.py startapp myapp

Now your tom should have a new folder in the root directory called
“myapp”. Next we need to tell Django to use this new application. In
your ``settings.py`` file file the ``INSTALLED_APPS`` settings and add
``myapp.apps.MyappConfig`` to the array:

.. code:: python

   INSTALLED_APPS = [
       'django.contrib.admin',
       ...
       'myapp.apps.MyappConfig'
   ]

Now we are read to start writing our new commands.

Writing the command
^^^^^^^^^^^^^^^^^^^

Let’s walk through a command to download observation data every hour.
The first thing to be done is to create a ``management/commands``
directory within your application to house our script. We’ll call it
``save_data.py``. The structure should look like this:

::

   mytom/
   ├── manage.py
   └── myapp/
       ├── __init__.py
       ├── models.py
       ├── tests.py
       ├── views.py
       └── management/
           └── commands/
               └── save_data.py

A management command simply needs a class called ``Command`` that
inherits from ``BaseCommand``, and a ``handle`` class method that
contains the logic for the command.

.. code:: python

   from django.core.management.base import BaseCommand
   from tom_observations.models import ObservationRecord


   class Command(BaseCommand):

       help = 'Downloads data for all completed observations'

       def handle(self, *args, **options):

Now, we need to add the logic to query the facilities for data. We’ll
iterate over each incomplete ``ObservationRecord``, and save the data
products locally for that ObservationRecord.

.. code:: python

   observation_records = ObservationRecord.objects.all()
   for record in observation_records:
       if record.terminal:
           record.save_data()

   return 'Success!'

So our final management command should look like this:

.. code:: python

   from django.core.management.base import BaseCommand
   from tom_observations.models import ObservationRecord


   class Command(BaseCommand):

       help = 'Downloads data for all completed observations'

       def handle(self, *args, **options):
           observation_records = ObservationRecord.objects.all()
           for record in observation_records:
               if record.terminal:
                   record.save_data()

           return 'Success!'

Adding parameters
^^^^^^^^^^^^^^^^^

Management commands also provide the ability to accept parameters. Doing
this is as simple as implementing ``add_arguments`` as a class method on
your ``Command`` class. Let’s say we want to ensure that our command can
be run for a single target:

.. code:: python

     def add_arguments(self, parser):
       parser.add_argument('--target_id', help='Download data for a single target')

That code will process any additional parameters, and we simply need to
handle them in our, ``handle`` class method. We’ll attempt to fetch the
supplied target from the database and filter the ObservationRecords
accordingly:

.. code:: python

     def handle(self, *args, **options):
       if options['target_id']:
         try:
           target = Target.objects.get(pk=options['target_id'])
           observation_records = ObservationRecord.objects.filter(target=target)
         except ObjectDoesNotExist:
           raise Exception('Invalid target id provided')
       else:
           observation_records = ObservationRecord.objects.all()
       ...

Finally, we filter our initial set of observation records, so this line:

.. code:: python

       observation_records = ObservationRecord.objects.all()

will become this:

.. code:: python

       observation_records = ObservationRecord.objects.filter(target=target)

And our final finished command looks as follows:

.. code:: python

   from django.core.management.base import BaseCommand
   from tom_observations.models import ObservationRecord
   from tom_targets.models import Target


   class Command(BaseCommand):

       help = 'Downloads data for all completed observations'

       def add_arguments(self, parser):
           parser.add_argument('--target_id', help='Download data for a single target')

       def handle(self, *args, **options):
           if options['target_id']:
               try:
                   target = Target.objects.get(pk=options['target_id'])
                   observation_records = ObservationRecord.objects.filter(target=target)
               except Target.DoesNotExist:
                   raise Exception('Invalid target id provided')
           else:
               observation_records = ObservationRecord.objects.all()
           for record in observation_records:
               if record.terminal:
                   record.save_data()

           return 'Success!'

Automating a management command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using cron
^^^^^^^^^^

On Unix-based systems, `cron <https://linux.die.net/man/8/cron>`__ can
be used to automate running of a Django management command. The syntax
is very simple, as commands look like this:

``30 2 * 6 3 /path/to/command /path/to/parameters``

In the above case, the first five values, which can either be numbers or
asterisks, represent elements of time. From left to right, they are
minutes, hours, day of the month, month of the year, and day of the
week. Our example would run a command every Wednesday (fourth day of the
week, starting from 0) in June (sixth month of the year, starting from
1) at 2:30 AM.

Websites like `crontab.guru <https://crontab.guru/>`__ make it easier to
reason about crontab expressions.

Scheduling can be made more complex as well–values can be
comma-separated or presented as a range. Refer to the abundance of cron
documentation for more information. An excellent beginner’s guide can be
found
`here <https://www.ostechnix.com/a-beginners-guide-to-cron-jobs/>`__.

Now, how is cron called? Well, cron jobs are run by the system, and it
reads the commands that need to be called from a cron table, or crontab.
To edit this file, simple call ``crontab -e``.

Using cron with a management command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To make this more specific to our example, let’s say we want to update
the observation data every hour. The command we would normally run in
our project directory would be the following:

``python manage.py save_data``

However, cron is a system-level operation, so the command needs to be
directory-agnostic, and we need to ensure we’re using the right Python
version. If you have a virtualenv, the command should be the absolute
path to the Python interpreter in the virtualenv. If your TOM is in a
Docker container, it should be the version of Python running in the
container. Otherwise, just ensure that it’s at least version 3.6 or
higher.

So, the line in our crontab should be as follows:

``0 * * * * /path/to/virtualenv/bin/python /path/to/project/manage.py save_data``

This will run every day on the hour. And that’s it! Just exit the
crontab and it will automatically restart cron, then your command will
run on the next hour.
