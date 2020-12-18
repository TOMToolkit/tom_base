Changing How Observations are Submitted
---------------------------------------

The LCO Observation module for the TOM Toolkit ships with a default HTML
form that facilitates submitting basic observations to the LCO network.
It may sometimes be desirable to customize the form to show or hide
fields, add new parameters, or change the submission logic itself,
depending on the needs of the project. In this tutorial we will
customize our LCO module to submit multiple observations with different
filters at the same time.

This guide assumes you have followed the `getting
started </introduction/getting_started>`__ guide and have a working TOM
up and running.

Create a new Observation Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Many methods of customizing the TOM Toolkit involve inheriting/extending
existing functionality. This time will be no different: we’ll crate a
new observation module that inherits the existing functionality from
``tom_observations.facilities.LCOFacility``.

First, create a python file somewhere in your project to house your new
module. For example it could live next to your ``settings.py``, or if
you’ve started a new app, it could live there. It doesn’t really matter,
as long as it’s located somewhere in your project:

::

   touch mytom/mytom/lcomultifilter.py

Now add some code to this file to create a new observation module:

.. code:: python

   # lcomultifilter.py
   from tom_observations.facilities.lco import LCOFacility


   class LCOMultiFilterFacility(LCOFacility):
       name = 'LCOMultiFilter'

So what does the above code do?

1. Line 1 imports the LCOFacility that is already shipped with the TOM
   Toolkit. We want this class because it contains functionality we will
   re-use in our own implementation.
2. Line 4 defines a new class named ``LCOMultiFilterFacility`` that
   inherits from ``LCOFacility``.
3. Line 5 sets the name attribute of this class to ``LCOMultiFilter``.

What you have done is created a new observation module that is
functionally identical to the existing LCO module, but has a different
name: ``LCOMultiFilter``. A good start!

Now we need to tell our TOM where to find our new module so we can use
it to submit observations. Add (or edit) the following lines to your
``settings.py``:

.. code:: python

   # settings.py
   TOM_FACILITY_CLASSES = [
       'tom_observations.facilities.lco.LCOFacility',
       'tom_observations.facilities.gemini.GEMFacility',
       'mytom.lcomultifilter.LCOMultiFilterFacility',
   ]

This code lists all of the observation modules that should be available
to our TOM.

With that done, go to any target in your TOM and you should see your new
module in the list:

|image0|

You could now use the new module now to make an observation, and it
would work the same as the old LCO module.

Note that if you see an error like: “There was a problem authenticating
with LCO” then you need to `add your LCO api
key </docs/customsettings#facilities>`__ to your ``settings.py`` file.

Adding additional fields
~~~~~~~~~~~~~~~~~~~~~~~~

Now that you’ve created a new observation module that’s functionally the
same as the old LCO module, how do we change it? One thing that might be
useful is to add some extra fields to the form: two more choices of
filters and exposure times. Back in the ``lcomultifilter.py`` file add a
new import and create a new class that will become the new form:

.. code:: python

   # lcomultifilter.py
   from tom_observations.facilities.lco import LCOFacility, LCOBaseObservationForm, filter_choices
   from django import forms


   class LCOMultiFilterForm(LCOBaseObservationForm):
       filter2 = forms.ChoiceField(choices=filter_choices)
       exposure_time2 = forms.FloatField(min_value=0.1)
       filter3 = forms.ChoiceField(choices=filter_choices)
       exposure_time3 = forms.FloatField(min_value=0.1)


   class LCOMultiFilterFacility(LCOFacility):
       name = 'LCOMultiFilter'
       form = LCOMultiFilterForm

There is now a new class, ``LCOMultiFilterForm`` which inherits from
``LCOBaseObservationForm``, the form for the default interface. Additionally
there are definitions for 4 fields: ``fiter2``, ``exposure_time2``,
``filter3``, and ``exposure_time3``.

A ``form`` attribute has been added on the ``LCOMultiFilterFacility``
class, this tells our observation module to use the new
``LCOMultiFilterForm`` instead of the default LCO observation form.

Modifying the form layout
~~~~~~~~~~~~~~~~~~~~~~~~~

Now that the desired fields have been added to the
``LCOMultiFilterForm``, the form’s layout needs to be modified in order
to actually display them. In this example we’ll split the form into two
rows: one row for the three filter choices and exposure times, and
another row for everything else. Note that the default form already has
fields for ``filter`` and ``exposure_time``, so we’ll overwrite the
entire layout so that they appear next to the new fields we added.

The ``LCOBaseObservationForm`` has a method ``layout()`` that returns the
desired layout using the `crispy forms
Layout <https://django-crispy-forms.readthedocs.io/en/d-0/layouts.html>`__
class. Familiarizing yourself with the basic functionality of crispy
forms would be a good idea if you wish to deeply customize your
observation module’s form.

With our modified layout added, the ``lcomultifilter.py`` file now looks
like this:

.. code:: python

   # lcomultifilter.py
   from tom_observations.facilities.lco import LCOFacility, LCOBaseObservationForm, filter_choices
   from django import forms
   from crispy_forms.layout import Div


   class LCOMultiFilterForm(LCOBaseObservationForm):
       filter2 = forms.ChoiceField(choices=filter_choices)
       exposure_time2 = forms.FloatField(min_value=0.1)
       filter3 = forms.ChoiceField(choices=filter_choices)
       exposure_time3 = forms.FloatField(min_value=0.1)

       def layout(self):
           return Div(
                   Div(
                       Div(
                           'name', 'proposal', 'ipp_value', 'observation_type', 'start', 'end',
                           css_class='col'
                       ),
                       Div(
                           'instrument_name', 'exposure_count', 'max_airmass',
                           css_class='col'
                       ),
                       css_class='form-row'
                   ),
                   Div(
                       Div(
                           'filter', 'exposure_time',
                           css_class='col'
                       ),
                       Div(
                           'filter2', 'exposure_time2',
                           css_class='col'
                       ),
                       Div(
                           'filter3', 'exposure_time3',
                           css_class='col'
                       ),
                       css_class='form-row'
                   )
           )


   class LCOMultiFilterFacility(LCOFacility):
       name = 'LCOMultiFilter'
       form = LCOMultiFilterForm

Take a look at the layout and compare it to the `existing lco
layout <https://github.com/TOMToolkit/tom_base/blob/main/tom_observations/facilities/lco.py#L169>`__.
A second row has been added that includes all the filter choices. Note
that the original ``filter`` and ``exposure_time`` have been moved from
their original location to the new row.

Now if you select “LCOMultiFilter” from the list of observation
facilities on a target you should see your new form:

|image1|

Is the form still too ugly for you? Trying playing with the layout
definition to suit your needs.

Changing the form submission behavior
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are not familiar with the `LCO submission
API <https://developers.lco.global/#observations>`__ now might be a good
time to take a look. The LCO Observation module uses this API to submit
observations using the data provided in the form, so we need to modify
how this happens. More specifically, we’d like to add two additional
``Configuration`` to our observation request, one for each of our
additional filters and exposure times.

Using the ``observation_payload()`` method, we can use ``super()`` to
get the original LCO module’s observation request, then modify it to
suit the needs of our ``LCOMultiFilter`` class:

.. code:: python

   #lcomultifilter.py
   from tom_observations.facilities.lco import LCOFacility, LCOBaseObservationForm, filter_choices
   from django import forms
   from crispy_forms.layout import Div
   from copy import deepcopy

   class LCOMultiFilterForm(LCOBaseObservationForm):
       filter2 = forms.ChoiceField(choices=filter_choices)
       exposure_time2 = forms.FloatField(min_value=0.1)
       filter3 = forms.ChoiceField(choices=filter_choices)
       exposure_time3 = forms.FloatField(min_value=0.1)

       def layout(self):
           return Div(
                   Div(
                       Div(
                           'name', 'proposal', 'ipp_value', 'observation_type', 'start', 'end',
                           css_class='col'
                       ),
                       Div(
                           'instrument_type', 'exposure_count', 'max_airmass',
                           css_class='col'
                       ),
                       css_class='form-row'
                   ),
                   Div(
                       Div(
                           'filter', 'exposure_time',
                           css_class='col'
                       ),
                       Div(
                           'filter2', 'exposure_time2',
                           css_class='col'
                       ),
                       Div(
                           'filter3', 'exposure_time3',
                           css_class='col'
                       ),
                       css_class='form-row'
                   )
           )

       def observation_payload(self):
           payload = super().observation_payload()
           configuration2 = deepcopy(payload['requests'][0]['configurations'][0])
           configuration3 = deepcopy(payload['requests'][0]['configurations'][0])
           configuration2['instrument_configs'][0]['optical_elements']['filter'] = self.cleaned_data['filter2']
           configuration2['instrument_configs'][0]['exposure_time'] = self.cleaned_data['exposure_time2']
           configuration3['instrument_configs'][0]['optical_elements']['filter'] = self.cleaned_data['filter3']
           configuration3['instrument_configs'][0]['exposure_time'] = self.cleaned_data['exposure_time3']
           payload['requests'][0]['configurations'].extend([configuration2, configuration3])
           return payload


   class LCOMultiFilterFacility(LCOFacility):
       name = 'LCOMultiFilter'
       form = LCOMultiFilterForm

Let’s go over what we did in this new ``observation_payload()`` method:

1. Line 1: We call ``super().observation_payload()`` to get the
   observation request which the parent class (LCOFacility) would have
   called.
2. Line 2-3 We copy the Request’s Configuration into two new
   Configurations: ``configuration2`` and ``configuration3``. These will
   be the additional Configuration we send to LCO.
3. Lines 5-8: We set the value of these new Configuration ``filter`` and
   ``exposure_time`` to the values we collected from our custom form.
4. lines 10-11: Finally, we extend the original Request’s Configuration
   array to include the 2 new Configuration we built. Return it and
   we’re done!

If you submit an observation request with the ``LCOMultiFilter``
observation module now you should see that it creates an observation
request with LCO with three Configuration!

Summary
~~~~~~~

Our original requirement was to be able to submit observations to LCO
with some additional filters and exposure times. We accomplished this
by:

1. Creating a new observation module: a ``LCOMultiFilterFacility`` class
   and a ``LCOMultiFilterForm``, both of which were child classes of the
   original ``LCOFacility`` class (since we wanted to keep most of the
   functionality intact) and then added this new class to our
   ``TOM_FACILITY_CLASSES`` setting.

2. We added a few fields to ``LCOMultiFilterForm`` and modified it’s
   layout to include these new fields using ``layout()``.

3. We implemented the ``LCOMultiFilterForm`` ``observation_payload()``
   which used the parent’s class return value and then modified it to
   suit our needs.

This is a good example of Object Oriented Programming in Python. If you
are curious about how this all works, we recommend reading up on OOP in
general, as well as how objects in Python 3 work.

.. |image0| image:: /_static/customize_observations/observebutton.png
.. |image1| image:: /_static/customize_observations/newform.png
