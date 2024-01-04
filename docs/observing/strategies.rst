Dynamic Cadences and Observation Templates
==========================================

The TOM has a couple of unique concepts that may be unfamiliar to some
at first, that will be describe here before going into detail.

The first concept is that of an observation template. If an observer is consistently
submitting observations with a lot of similar parameters, it may be
useful to save those as a kind of template, which can just be loaded
later. The TOM Toolkit offers an interface that allows facilities to
define a template form, that will be saved as an observation template. The
template can then be applied to an observation, with the remaining
parameters filled in or changed. An observation template can also be
creating from a past observation, with a button to do so that’s
available on any ObservationRecord detail page.

The second concept referred to is a dynamic cadence. A cadence is as it
sounds–a series of observations that are performed at regular intervals.
However, most observatories don’t have built-in support for cadences,
and, if they do, they may be limited to a predetermined cadence. The TOM
Toolkit, on the other hand, allows for a *dynamic* cadence. Because
data is collected programmatically, and observations are submitted
programmatically, a user can write their own cadence strategy to submit
observations depending on the success of a prior observation or the data
collected from a prior observation.

Writing a custom dynamic cadence
---------------------------------

Many of the TOM modules leverage a plugin architecture that enables you
to write your own implementation, and the cadence strategy plugin is no
different. If you’re familiar with the other modules, you’ve already
seen examples of this in the
`Writing an alert broker <../customization/create_broker>`__,
`Writing an observation module <observation_module>`__, and
`Customizing data processing <../customization/customizing_data_processing>`__
tutorials.

Create a cadence strategy file
------------------------------

First, you’ll need a file where you’ll put your custom cadence strategy.
If you have a fresh TOM installation, you’ll have a directory structure
that looks something like this:

::

   ├── data
   ├── db.sqlite3
   ├── manage.py
   ├── mytom
   │   ├── __init__.py
   │   ├── settings.py
   │   ├── urls.py
   │   └── wsgi.py
   ├── static
   ├── templates
   └── tmp

We’ll create a new file called ``mycadence.py`` and place it next to
``settings.py``. To get started, we’ll just put a small skeleton into
our new file, so to begin with, it should look like this:

.. code:: python

   from tom_observations.cadence import CadenceStrategy

   class MyCadenceStrategy(CadenceStrategy):
     pass

We also need to add the cadence strategy to ``settings.py`` so that our
TOM knows that it exists:

.. code:: python

   TOM_CADENCE_STRATEGIES = [
       'tom_observations.cadence.RetryFailedObservationsStrategy',
       'tom_observations.cadence.ResumeCadenceAfterFailureStrategy',
       'mytom.mycadence.MyCadenceStrategy'
   ]

Add logic to the new cadence strategy
-------------------------------------

You may have noticed that our ``MyCadenceStrategy`` class inherits from
``CadenceStrategy``. The ``CadenceStrategy`` interface only has one
method, which is ``run()``. All of the logic for a ``CadenceStrategy``
lives in the ``run()`` method. Rather than demonstrating the
implementation of a new cadence strategy, this tutorial is going to walk
through the business logic of a built-in cadence strategy. We’re going
to review the ``ResumeCadenceAfterFailureStrategy``.

It should also be worth mentioning at this point that the
``CadenceStrategy`` constructor takes a ``dynamic_cadence``. The
``dynamic_cadence`` is the association of the cadence strategy and the 
observation group that make up the cadence, and is created in the 
``ObservationCreateView`` when the first observation of a cadence is submitted.

The ``ResumeCadenceAfterFailureStrategy`` is designed to ensure that,
even after an observation fails, the cadence remains consistent. If, for
example, you submit an observation with a cadence of three days, and the
observation fails, the cadence should attempt to get the observation as
soon as possible, and then resume observing once every three days.

Let’s look at the strategy piece by piece.

.. code:: python

   last_obs = self.dynamic_cadence.observation_group.observation_records.order_by('-created').first()
   facility = get_service_class(last_obs.facility)()
   facility.update_observation_status(last_obs.observation_id)
   last_obs.refresh_from_db()

The first thing this strategy does is get a couple of pieces of
information. First, from the observation group that the cadence consists
of, the most recent observation is selected. The facility class for the
facility that the cadence is submitting observations to is also
instantiated. With these values, the status of the most recent cadence
observation is updated, and the ``ObservationRecord`` object is
refreshed.

.. code:: python

   start_keyword, end_keyword = facility.get_start_end_keywords()
   observation_payload = last_obs.parameters_as_dict
   new_observations = []

These lines are, again, just more setup. Each facility has its own
unique keywords representing the start and the end of the observation
window, so we get those from the facility class. Then, we get the
original observation parameters that were submitted to the facility, and
we initialize a list for any new observations that will be submitted
when the cadence is updated.

.. code:: python

   if not last_obs.terminal:
       return
   elif last_obs.failed:
       # Submit next observation to be taken as soon as possible
       window_length = parse(observation_payload[end_keyword]) - parse(observation_payload[start_keyword])
       observation_payload[start_keyword] = datetime.now().isoformat()
       observation_payload[end_keyword] = (parse(observation_payload[start_keyword]) + window_length).isoformat()
   else:
       # Advance window normally according to cadence parameters
       observation_payload = self.advance_window(
           observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
       )

Here we have some logic for the three cases–either the most recent
observation hasn’t happened yet, it failed, or it succeeded. If it
hasn’t happened, then there’s nothing to do–we’ll check again later. If
if failed, we want to submit it again to be taken immediately, so we get
the original length of the observation window, and set our new
observation payload to start immediately, and end such that the new
window length is the same. Finally, if our observation succeeded, we
update our new observation parameters to start 72 hours after the last
observation, using a utility method that’s part of the
``ResumeCadenceAfterFailureStrategy`` called ``advance_window``.

.. code:: python

   obs_type = last_obs.parameters_as_dict.get('observation_type')
   form = facility.get_form(obs_type)(data=observation_payload)
   form.is_valid()
   observation_ids = facility.submit_observation(form.observation_payload())

   for observation_id in observation_ids:
       # Create Observation record
       record = ObservationRecord.objects.create(
           target=last_obs.target,
           facility=facility.name,
           parameters=json.dumps(observation_payload),
           observation_id=observation_id
       )
       self.dynamic_cadence.observation_group.observation_records.add(record)
       self.dynamic_cadence.observation_group.save()
       new_observations.append(record)

       for obsr in new_observations:
           facility = get_service_class(obsr.facility)()
           facility.update_observation_status(obsr.observation_id)

       return new_observations

The last part of our strategy is when we submit our new observations.
Regardless of how we modified the observing window, we initialize our
observation form, validate it, and submit the observation to our
facility. The rest of the code is saving any resulting observations to
the database, getting their new status from the facility, and returning
them.

Just to review, here is the strategy’s ``run()`` in its entirety:

.. code:: python

   def run(self):
        last_obs = self.dynamic_cadence.observation_group.observation_records.order_by('-created').first()
        facility = get_service_class(last_obs.facility)()
        facility.update_observation_status(last_obs.observation_id)
        last_obs.refresh_from_db()
        start_keyword, end_keyword = facility.get_start_end_keywords()
        observation_payload = last_obs.parameters_as_dict
        new_observations = []
        if not last_obs.terminal:
            return
        elif last_obs.failed:
            # Submit next observation to be taken as soon as possible
            window_length = parse(observation_payload[end_keyword]) - parse(observation_payload[start_keyword])
            observation_payload[start_keyword] = datetime.now().isoformat()
            observation_payload[end_keyword] = (parse(observation_payload[start_keyword]) + window_length).isoformat()
        else:
            # Advance window normally according to cadence parameters
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )

        obs_type = last_obs.parameters_as_dict.get('observation_type')
        form = facility.get_form(obs_type)(data=observation_payload)
        form.is_valid()
        observation_ids = facility.submit_observation(form.observation_payload())

        for observation_id in observation_ids:
            # Create Observation record
            record = ObservationRecord.objects.create(
                target=last_obs.target,
                facility=facility.name,
                parameters=json.dumps(observation_payload),
                observation_id=observation_id
            )
            self.dynamic_cadence.observation_group.observation_records.add(record)
            self.dynamic_cadence.observation_group.save()
            new_observations.append(record)

        for obsr in new_observations:
            facility = get_service_class(obsr.facility)()
            facility.update_observation_status(obsr.observation_id)

        return new_observations

Configuring the cadence strategy to run automatically
-----------------------------------------------------

As you may have noticed, the cadence strategies act on updates to the
status of an ``ObservationRecord``. Ideally, we want the cadence
strategies to run as soon as an observation status changes–so, we need
to automate that and have it run periodically.

Fortunately, the TOM Toolkit comes with a built-in management command to
update all cadences in the TOM. If you’ve perused the TOM Toolkit
documentation previously, you may have noticed a section about
automation of tasks, and, more specifically, a subsection about
:doc:`Using cron with a management command <../code/automation>`.
You can simply apply the instructions here, but use the management
command ``runcadencestrategies.py`` in place of the example. If you set
your cron to run every few minutes or so, you’ll ensure that your
cadences are kept up to date!
