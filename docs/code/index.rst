Interacting with your TOM through code
======================================

TOM systems provide a platform for automating some, if not all, of the day-to-day workflow of an
astronomical program.  To that end, the Toolkit offers Application Programmable Interfaces (API) for
a number of key functions, and there are a number of options for automating workflows.

Automated Tasks
---------------

There are many tasks which often have to be executed on a regular schedule, such as looking for new potential
targets for instance.  Rather than have to do this yourself, you can write a simple script called a ``management command``
which can be configured to run regularly as a cronjob.

This mechanism is also really helpful if you want to implementing code to analyse the data in the TOM without having to
build it into the user interface.

:doc:`Automating Tasks </code/automation>` describes how to implement a ``management command``, and a full list of the
TOM's built-in management commands can be found :doc:`here </api/management_commands>`.

Asynchronous Tasks
------------------

Sometimes functions can take a long time to complete, such as data reduction pipelines or queries to external services.
This can be an issue for browser-based systems like TOMs, because the browser has a timeout which may raise an error
before the task completes.  Nevertheless, it is often desirable for a TOM system to be able to orchestrate these
tasks.

An asynchronous task is designed to mitigate this problem; it can be triggered to run in the background by the TOM, and
to return the expected output whenever it is ready.  :doc:`Background Tasks </code/backgroundtasks>` describes how to set up
an asynchronous task library to handle long running and/or concurrent functions.

Advanced Queries
----------------

Django's QuerySet API provides a range of sophisticated and efficient tools for querying your TOM's database.
:doc:`Advanced Querying </code/querying>` explores some of the options in more depth.

Custom Code Hooks
-----------------

A code hook allows us to tell the TOM to perform a given function whenever a certain action is taken, such as clicking
a button or uploading a file.  You can add your own customized functions to the TOM and define when they should
be called following the guidelines in :doc:`Running Custom Code Hooks </code/custom_code>`.

Python Scripts and Jupyter Notebooks
------------------------------------

You can also interact directly with your TOM from a Python script or Jupyter notebook, which provides a flexible way to
analysis the data.  :doc:`Scripting your TOM with Jupyter Notebooks </common/scripts>` shows how.

TOM Toolkit APIs
----------------

Full details of all TOM Toolkit functions can be found in the :doc:`API Documentation </api/modules>`.