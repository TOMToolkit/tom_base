Running asynchronous background tasks
-------------------------------------

When you are using your TOM via the web interface, the code that is
running in the background is tied to the request/response cycle. What
this means is that when you click a button or link in the TOM, your
browser constructs a web request, which is then sent to the web server
running your TOM. The TOM receives this request and then runs a bunch of
code, ultimately to generate a response that gets sent back to the
browser. This response is what you see when the next page loads. For the
purposes of this explanation, this all happens *synchronously*, meaning
that your browser has to wait for your TOM to respond before displaying
the next page.

::

   ----------   request        ----------
   |         | ------------->  |        |
   | browser |  response       |  TOM   |
   |         | <-------------  |        |
   ----------                  ----------

But what happens if your TOM performs some compute or IO heavy task
while constructing the response? One example would be running a source
extraction on a data product after a user uploads it to your TOM.
Normally, the browser will just wait for the response. This results in
an agonizing wait time for the user as they watch the browser’s loading
spinner slowly rotate. Eventually they will give up and either reload
the page or close it completely. In fact, according to a study by
Akamai, 50% of web users will not wait longer than 10-15 seconds for a
page to load before giving up.

The way we avoid these wait times is to run our slow code
*asynchronously* in the background, in a separate thread or process. In
this model the TOM responds to the browser with a response immediately,
before the slow code has even finished.

::

   ----------   request        ----------   task     -----------
   |         | ------------->  |        | -------->  |         |
   | browser |  response       |  TOM   |   result   | worker  |
   |         | <-------------  |        | <--------  |         |
   ----------                  ----------            -----------

A very common scenario is sending email. Many web applications require
the functionality of sending mail at some point. Let’s say the PI of a
project has the option to mass notify their CIs that observations have
been taken. Usually, sending email takes a very short amount of time,
but it is still good practice to remove it from the request/response
cycle, just in case it takes longer than usual or errors in some way.

In this tutorial, we will go over how to run tasks asynchronously in
your TOM if you have the need to do so.

Running tasks with Dramatiq
~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Dramatiq <https://dramatiq.io/>`__ is a task processing library for
python. Simply put: it allows you to define functions as *actors* and
then execute those function using *workers*. None of this can happen
without a *broker*, though, which is the piece that is responsible for
passing messages from the *web process* to the *workers*.

Installing Redis
^^^^^^^^^^^^^^^^

Unfortunately, the broker is a separate piece of software outside of the
task library. Dramatiq supports using either RabbitMQ or Redis. We’ll
use Redis because of its versatility: not only can it be used as a
message broker but it can also be used in your TOM as a cache (though
not covered in this tutorial).

Depending on your OS, there are a few ways to `install
Redis <https://redis.io/download>`__.

Using Docker
''''''''''''

One of the easiest ways to install Redis is to use Docker:

::

   docker run --name tom-redis -d -p6379:6379 redis

Building from source
''''''''''''''''''''

You can also download Redis directly from the website and compile it:

::

   $ wget http://download.redis.io/releases/redis-5.0.5.tar.gz
   $ tar xzf redis-5.0.5.tar.gz
   $ cd redis-5.0.5
   $ make

You can now run the server with:

::

   ./src/redis-server

Using a package manager
'''''''''''''''''''''''

If you are running Linux, most likely Redis is included with your
distribution via its package manager. For example:

::

   apt install Redis

Whichever way works for you, we should now have a Redis server up and
running and listening on port 6379.

Installing Dramatiq
^^^^^^^^^^^^^^^^^^^

Now that we have our broker running, we can install and configure our
TOM to run Dramatiq. Start by installing the required dependencies into
your virtualenv:

::

   pip install 'dramatiq[watch, redis]' django-dramatiq

`django-dramatiq <https://github.com/Bogdanp/django_dramatiq>`__ will
offer us some conveniences while working with tasks in our TOM.

Install django-dramatiq to your ``INSTALLED_APPS`` setting, above the
tom_* apps:

.. code:: python

   INSTALLED_APPS = [
       ...
       'django_gravatar',
       'django_dramatiq',
       'tom_targets',
       ...
   ]

Add a section for dramatiq in ``settings.py``:

.. code:: python

   DRAMATIQ_BROKER = {
       "BROKER": "dramatiq.brokers.redis.RedisBroker",
       "OPTIONS": {
           "url": "redis://localhost:6379",
       },
       "MIDDLEWARE": [
           "dramatiq.middleware.AgeLimit",
           "dramatiq.middleware.TimeLimit",
           "dramatiq.middleware.Callbacks",
           "dramatiq.middleware.Retries",
           "django_dramatiq.middleware.AdminMiddleware",
           "django_dramatiq.middleware.DbConnectionsMiddleware",
       ]
   }

If you want to store the results of your tasks add a section in
``settings.py`` for that as well:

.. code:: python

   DRAMATIQ_RESULT_BACKEND = {
       "BACKEND": "dramatiq.results.backends.redis.RedisBackend",
       "BACKEND_OPTIONS": {
           "url": "redis://localhost:6379",
       },
       "MIDDLEWARE_OPTIONS": {
           "result_ttl": 60000
       }
   }

Now that all the settings are in place, we need to run a
``manage.py migrate`` in order to create the ``django_dramatiq`` table.
Then, we can test installation by starting up some workers:

::

   ./manage.py rundramatiq

If all goes well you will see output that looks like this:

::

   % ./manage.py rundramatiq
    * Discovered tasks module: 'django_dramatiq.tasks'
    * Running dramatiq: "dramatiq --path . --processes 8 --threads 8 --watch . django_dramatiq.setup django_dramatiq.tasks"

   [2019-08-21 17:52:30,216] [PID 27267] [MainThread] [dramatiq.MainProcess] [INFO] Dramatiq '1.6.1' is booting up.
   Worker process is ready for action.

Your task workers are up and running!

Writing a task
^^^^^^^^^^^^^^

Now that we have some workers, lets put them to work. In order to do
that we’ll write a task.

Create a file ``mytom/myapp/tasks.py`` where ``myapp`` is a django app
you’ve installed into ``INSTALLED_APPS``. If you haven’t started one,
you can do so with:

::

   ./manage.py startapp myapp

In ``tasks.py``:

.. code:: python

   import dramatiq
   import time
   import logging

   logger = logging.getLogger(__name__)


   @dramatiq.actor
   def super_complicated_task():
       logger.info('starting task...')
       time.sleep(2)
       logger.info('still running...')
       time.sleep(2)
       logger.info('done!')

This task will emulate a function that blocks for 4 seconds, in practice
this would be a network call or some kind of heavy processing task.

Now open up a Django shell:

::

   ./manage.py shell_plus

And import and call the task:

::

   In [1]: from myapp.tasks import super_complicated_task

   In [2]: super_complicated_task.send()
   Out[2]: Message(queue_name='default', actor_name='super_complicated_task', args=(), kwargs={}, options={'redis_message_id': '667821da-f236-4c4e-969a-9d1f1ff54be2'}, message_id='2c8893d8-4211-4cac-b0b9-0f2e9672d0ae', message_timestamp=1566416600481)

In the terminal where you started the dramatiq workers (not the django
shell!) you should see the following output:

::

   starting task...
   still running...
   done!

Notice how calling the task returned immediately in the shell, but the
task took a few seconds to complete. This is how it would work in
practice in your django app: Somewhere in your code, for example in your
app’s ``views.py``, you would import the task just like we did in the
terminal. Now when the view gets called, the task will be queued for
execution and the response can be sent back to the user’s browser right
away. The task will finish in the background.

Conclusion
^^^^^^^^^^

In this tutorial we went over the need for asynchronous tasks, the
installation of Dramatiq and the broker, and finally writing a running a
task.

We recommend reading the `Dramatiq <https://dramatiq.io/guide.html>`__
documentation for full details on what the library is capable of, as
well as additional usage examples.
