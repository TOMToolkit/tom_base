Running Custom Code on Actions in your TOM
------------------------------------------

Sometimes it would be desirable for your TOM to run custom code when
certain actions happen. For example: when an observation is completed
you’d like to submit your data to an outside service. Or when you add a
new target you’d like to automatically search a remote catalog for
matches. You could even make your TOM automatically tweet new
observations! We can achieve these tasks using code hooks.

An example code hook: send an email when observation completes.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this example, we’ll write a little bit of code to send an email when
an observation record changes it’s state to ‘COMPLETED’. We’ll assume
you have gone through the `getting
started </introduction/getting_started>`__ guide, and that you have
working TOM up and running called mytom.

First, let’s create a python module where the entry point to our custom
code will live:

::

   touch mytom/hooks.py

Inside this module, let’s stub out a method to call when our observation
changes status:

.. code:: python

   import logging

   logger = logging.getLogger(__name__)


   def observation_change_state(observation, previous_status):
       logger.info(
           'Sending email, observation %s changed state from %s to %s',
           observation, previous_status, observation.status
       )

This method, for now, will simply log the fact that we will send out an
email. Note that the method takes the observation and it’s previous
status as parameters.

Next, we’ll tell our TOM to execute this method when an observation
changes state. This is done via the ``HOOKS`` configuration parameter in
your project’s ``settings.py``:

.. code:: python

   HOOKS = {
       'target_post_save': 'tom_common.hooks.target_post_save',
       'observation_change_state': 'mytom.hooks.observation_change_state',
       'data_product_post_upload': 'tom_dataproducts.hooks.data_product_post_upload',
   }

We changed the path for the ``observation_change_state`` method from
it’s default to the module path for our custom method,
``mytom.hooks.observation_change_state``.

Now, when an observation changes state, you should see the following in
your logs:

::

   Sending email, observation M42 @ LCO changed state from PENDING to COMPLETED

You can test this by manually changing an observation via the `django
admin
page <http://127.0.0.1:8000/admin/tom_observations/observationrecord/>`__.

If you only wanted to know how to run code via a hook, you can stop here
and implement your own code hooks. If you’d like to learn how to send an
email, read on.

Sending email
~~~~~~~~~~~~~

Django has `good
support <https://docs.djangoproject.com/en/2.1/topics/email/>`__ for
sending emails, and you’ll need to read the documentation to get the
basic setup right. Once you have the proper settings configured, sending
an email in your hook becomes as simple as this:

.. code:: python

   import logging
   from django.core.mail import send_mail

   logger = logging.getLogger(__name__)


   def observation_change_state(observation, previous_status):
       if observation.status == 'COMPLETED':
           logger.info(
               'Sending email, observation %s changed state from %s to %s',
               observation, previous_status, observation.status
           )
           send_mail(
               'Observation complete',
               'The observation {} has completed'.format(observation),
               'from@mytom.com',
               ['to@example.com'],
               fail_silently=False,
           )

That is all that is necessary for sending an email, though you might
want to look into using asynchronous task runners such as
`dramatiq <https://dramatiq.io/>`__ or
`celery <http://www.celeryproject.org/>`__.

Available code hooks
~~~~~~~~~~~~~~~~~~~~

At present, there are three available code hooks.

-  target_post_save: Runs after a target is created or updated.
-  observation_change_state: Runs whenever an observation’s state is
   updated.
-  data_product_post_upload: Runs after a data product is successfully
   uploaded to the TOM.
-  data_product_post_save: Runs after a data product is saved from a facility.
-  multiple_data_products_post_save: Runs for all data products saved from a facility.

..

   **NOTE**: ``target_post_save`` does not run automatically following a
   programmatic create statement, such as:

   .. code:: python

      Target.objects.create(name='m51')
