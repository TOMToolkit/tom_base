LaTeX Generation
================

One of the features the TOM Toolkit offers is automated generation of
LaTeX-formatted data tables. The LaTeX table tool allows the user to
select the parameters for an entity in their TOM–for example, a
Target–and generate a table of those parameters for all targets within a
list. At the moment, the Toolkit supports table generation for two
built-in models–``ObservationGroup``\ s and ``TargetList``\ s.

A LaTeX processor can be created for any model, or, with some additional
modifications, any combination of models. The supported LaTeX processors
must be specified in ``settings.py`` in the ``TOM_LATEX_PROCESSORS`` as
key/value pairs, with the model being the key, and the processor class
being the value. By default, the following processors are automatically
present in ``settings.py``:

.. code-block:: python

   TOM_LATEX_PROCESSORS = {
       'ObservationGroup': 'tom_publications.processors.latex_processor.ObservationGroupLatexProcessor',
       'TargetList': 'tom_publications.processors.target_list_latex_processor.TargetListLatexProcessor'
   }

Custom Processing
-----------------

The built-in LaTeX table generation is good, but it certainly has some
shortcomings, and can’t be expected to cover every or even most use
cases. As such, the implementation allows for smooth addition of any
custom processing.

In order to generate a LaTeX table for a unique use case, we’ll need to
write a custom LaTeX processor, which we’ll go through below. A LaTeX
processor has a custom Form class and a Processor class, and the
Processor class has a function which takes data from your TOM DB and
outputs it in the preferred LaTeX-formatted table. To begin, here’s a
brief look at part of the structure of the tom_publications app in the
TOM Toolkit:

.. code-block::

   tom_publications
   ├──latex.py
   └──processors
      ├──target_list_latex_processor.py
      └──observation_group_latex_processor.py

Perhaps one wants a processor that generates a table simply for all the
photometric or spectroscopic data for a given target. The first thing to
be done is to create a ``target_photometry_latex_processor.py``. We’ll
create a new file for our processor, and then create a
``TargetListLatexProcessor`` class that inherits from
``GenericLatexProcessor``. ``GenericLatexProcessor`` has an abstract
method that must be implemented called ``create_latex``, so we’ll also
add that:

.. code-block:: python

   from tom_publications.latex import GenericLatexProcessor

   class TargetDataLatexProcessor(GenericLatexProcessor):

     def create_latex(self, cleaned_data):
       pass

The ``GenericLatexProcessor`` also has a form class that renders the
correct set of fields to be generated. In our case, we’d like the user
to be able to choose between spectroscopy or photometry. So let’s create
the form. We’ll also create one form field, and populate it with our two
choices:

.. code-block:: python

   from django import forms

   from tom_publications.latex import GenericLatexProcessor, GenericLatexForm


   class TargetDataLatexForm(GenericLatexForm):
     data_type = forms.ChoiceField(
       choices=[('spectroscopy', 'Spectroscopy'), ('photometry', 'Photometry')],
       required=True,
       widget=forms.RadioSelect()
     )


   class TargetDataLatexProcessor(GenericLatexProcessor):
   ...

With the form implemented, we can implement our ``create_latex`` method
and add our ``TargetDataLatexForm`` as the ``form_class``.

The base form class always includes ``model_pk``, which gives us a way
to access the object for which we’re generating data.

.. code-block:: python

   import json

   from django import forms

   from tom_dataproducts.models import ReducedDatum
   from tom_publications.latex import GenericLatexProcessor, GenericLatexForm
   from tom_targets.models import Target

   ...

   class TargetDataLatexProcessor(GenericLatexProcessor):
     form_class = TargetDataLatexForm

     def create_latex_table_data(self, cleaned_data):
       target = Target.objects.get(pk=cleaned_data.get('model_pk'))
       data = ReducedDatum.objects.filter(target=target, data_type=cleaned_data.get('data_type'))

       table_data = {}
       if cleaned_data.get('data_type') == 'photometry':
         for datum in data:
           for key, value in json.loads(datum.value).items():
             table_data.setdefault(key, []).append(value)
       elif cleaned_data.get('data_type') == 'spectroscopy':
         ...

       return table_data

The above example only shows the photometric table generation, but
spectroscopic can be left as an exercise to the reader.

The last two steps are to link our new processor to our existing code.
First, in our ``settings.py`` (making sure you replace the displayed
path with the correct one for your TOM):

.. code-block:: python

   ...
   TOM_LATEX_PROCESSORS = {
       'ObservationGroup': 'tom_publications.processors.latex_processor.ObservationGroupLatexProcessor',
       'TargetList': 'tom_publications.processors.target_list_latex_processor.TargetListLatexProcessor',
       'Target': 'tom_publications.processors.target_data_latex_processor.TargetDataLatexProcessor'
   }
   ...

We add a ``Target`` processor. For the default implementation, all
processors must be tied to a TOM model, but with a custom templatetag
(or enough requests to the developers), it can be expanded further.

Then, in our overridden ``target_detail.html`` template (details on
overriding templates can be found
`here <https://tom-toolkit.readthedocs.io/en/latest/customization/customize_templates.html>`__),
we add a button:

.. code-block:: html

   ...
   <div id="target-info">
         {% target_feature object %}
         {% latex_button object %}
         {% if object.future_observations %}
   ...

For context, the template tag being referenced by
``{% latex_button object %}`` can be seen below. It accepts an instance
of a model from your TOM and generates a button with the correct query
parameters to send to your form.

.. code-block:: python

   @register.inclusion_tag('tom_publications/partials/latex_button.html')
   def latex_button(object):
       """
       Renders a button that redirects to the LaTeX table generation page for the specified model instance. Requires an
       object, which is generally the object in the context for the page on which the templatetag will be used.
       """
       model_name = object._meta.label
       return {'model_name': object._meta.label, 'model_pk': object.id}

With all that done, you will now be able to generate tables of
photometric (and eventually spectroscopic) data of any target in your
TOM. Here’s our final ``target_data_latex_processor.py``:

.. code-block:: python

   import json

   from django import forms

   from tom_dataproducts.models import ReducedDatum
   from tom_publications.latex import GenericLatexProcessor, GenericLatexForm
   from tom_targets.models import Target


   class TargetDataLatexForm(GenericLatexForm):
       data_type = forms.ChoiceField(
           choices=[('spectroscopy', 'Spectroscopy'), ('photometry', 'Photometry')],
           required=True,
           widget=forms.RadioSelect()
       )


   class TargetDataLatexProcessor(GenericLatexProcessor):
       form_class = TargetDataLatexForm

       def create_latex_table_data(self, cleaned_data):
           target = Target.objects.get(pk=cleaned_data.get('model_pk'))
           data = ReducedDatum.objects.filter(target=target, data_type=cleaned_data.get('data_type'))

           table_data = {}
           if cleaned_data.get('data_type') == 'photometry':
               for datum in data:
                   for key, value in json.loads(datum.value).items():
                       table_data.setdefault(key, []).append(value)
           elif cleaned_data.get('data_type') == 'spectroscopy':
               ...

           return table_data
