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

Running tasks with django-tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
`django-tasks <https://github.com/django/deps/blob/a83080652411e34e6afa8e1f0a97b675a76358e5/accepted/0014-background-workers.rst>`__
is a reference implementation of Django’s official background tasks library.
It provides an interface for marking functions as tasks and a worker
for executing them. The database backend utilizes the Django ORM,
which makes it easy to get started without having to install any additional
software.

Setting up django-tasks in a TOM
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Check to make sure your TOM has django_tasks installed:

.. code-block:: python
    :caption: settings.py

    INSTALLED_APPS = [
        ...
        'django_tasks',
        'django_tasks.backends.database',
        ...
    ]

By default, the immediate mode is enabled which means tasks are not run
asynchronously. To enable asynchronous execution, you need to configure
the django_tasks to use a the database backend:

.. code-block:: python
    :caption: settings.py

    TASKS = {
        "default": {
             "BACKEND": "django_tasks.backends.database.DatabaseBackend"
            # "BACKEND": "django_tasks.backends.immediate.ImmediateBackend"
        }
    }

Running in immediate mode is still useful for development and testing.

Running the worker
^^^^^^^^^^^^^^^^^^

To run the worker, you can use the following command:

.. code:: bash

   ./manage.py db_worker -v3


The ``v`` parameter is the verbosity level, set it to 3 for debugging purposes.

Note that this command is run in addition to the Django development server, i.e. ``./manage.py runserver``.
You should now be ready to write and execute tasks.

Writing a task
^^^^^^^^^^^^^^

Now that we have some a worker, lets put it to work. In order to do
that we’ll write a task.

Create a file ``mytom/myapp/tasks.py`` where ``myapp`` is a django app
you’ve installed into ``INSTALLED_APPS``. If you haven’t started one,
you can do so with:

::

   ./manage.py startapp myapp

In ``tasks.py``:

.. code-block:: python
    :caption: mytom/myapp/tasks.py
    :linenos:

    from django_tasks import task
    import time
    import logging

    logger = logging.getLogger(__name__)


    @task
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
   In [2]: super_complicated_task.enqueue()
   Out[2]: TaskResult(task=Task(priority=0, func=<function super_complicated_task at 0x778d881c0e00>, backend='default', queue_name='default', run_after=None, enqueue_on_commit=None), id='f323fdc8-4088-424d-a4d4-74ad741c5c04', status=ResultStatus.NEW, enqueued_at=datetime.datetime(2025, 3, 13, 21, 13, 0, 8578, tzinfo=datetime.timezone.utc), started_at=None, finished_at=None, args=[], kwargs={}, backend='default', _exception_class=None, _traceback=None, _return_value=None, db_result=<DBTaskResult: DBTaskResult object (f323fdc8-4088-424d-a4d4-74ad741c5c04)>)

In the terminal where you started the task worker (not the django
shell!) you should see the following output:

::

    Task id=f323fdc8-4088-424d-a4d4-74ad741c5c04 path=tom_async_demo.views.super_complicated_task state=RUNNING
    starting task...
    still running...
    done!
    Task id=f323fdc8-4088-424d-a4d4-74ad741c5c04 path=tom_async_demo.views.super_complicated_task state=SUCCEEDED

Notice how calling the ``enqueue()`` function returned immediately in the shell, but the
task took a few seconds to complete. This is how it would work in
practice in your django app: Somewhere in your code, for example in your
app’s ``views.py``, you would import the task just like we did in the
terminal. Now when the view gets called, the task will be queued for
execution and the response can be sent back to the user’s browser right
away. The task will finish in the background.

A few more things about the ``enqueue()`` function: First, if your task function
takes any arguments, you pass them into the enqueue function. Secondly,
the object returned from this function is a TaskResult. This object can be used to
check the status of the task, retrieve its result, or cancel it.

A common pattern is to call ``enqueue()`` in a view function and pass the
result ID immediately in the response. This ID can be used to check the status of the task,
using the ``task.get_result()`` method, via polling or some other mechanism.

Conclusion
^^^^^^^^^^

In this tutorial we went over why asynchronous tasks are needed, the
installation of django-tasks, and finally writing a running a
task.

We recommend reading the `django-tasks <https://github.com/realOrangeOne/django-tasks>`__
documentation for full details on what the library is capable of, as
well as additional usage examples.
