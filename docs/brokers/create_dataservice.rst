Adding a Data Service Module for the TOM Toolkit
------------------------------------------------

This guide is to walk you step by step through the process of creating a Data Service.
This assumes that you want a user interface for querying your data service via a form.
Many of these steps can be skipped if your service is only intended to be accessed internally.

Once fully implemented, a dataservice should automatically show up in the proper nav bar drop downs, and be able to
query a service via a form, displaying results to a custom table, then finally saving desired results to a TOM's DB.

Setting up the Basic Data Service:
**********************************

First we will build the bare bones of our data service. This is the bare minimum to get the service to show up in the
TOM. We'll start with three pieces of generic code:

 - Our Query class (an extension of `tom_dataservices.dataservice.DataService`)
 - Our Form Class (an extension of `tom_dataservices.forms.BaseQueryForm`)
 - An integration point for our data service in ``Apps.py``


First the actual query class:
+++++++++++++++++++++++++++++


.. code-block:: python
    :caption: my_dataservice.py
    :linenos:

    from tom_dataservices.dataservices import DataService
    from my_dataservice.forms import MyServiceForm

    class MyDataService(DataService):
        """
        This is an Example Data Service with the minimum required 
        functionality.
        """
        name = 'MyService'

        @classmethod
        def get_form_class(cls):
            """
            Points to the form class discussed below.
            """
            return MyServiceForm
        
        def build_query_parameters(self, parameters, **kwargs):
            """
            Use this function to convert the form results into the query parameters understood
            by the Data Service.
            """
            return self.query_parameters
        
        def query_service(self, data, **kwargs):
            """
            This is where you actually make the call to the Data Service. 
            Return the results.
            """
            return self.query_results


Your Data Service needs a form:
+++++++++++++++++++++++++++++++

.. code-block:: python
    :caption: forms.py
    :linenos:

    from django import forms
    from tom_dataservices.forms import BaseQueryForm

    class MyServiceForm(BaseQueryForm):
        first_field = forms.CharField(required=False,
                                      label='An Example Field',
                                      help_text='Put important info here.')


Adding the integration point:
+++++++++++++++++++++++++++++

.. code-block:: python
    :caption: apps.py
    :linenos:

    from django.apps import AppConfig


    class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'my_app'

    def data_services(self):
        """
        integration point for including data services in the TOM
        This method should return a list of dictionaries containing dot separated DataService classes
        """
        return [{'class': f'{self.name}.my_dataservice.MyDataService'}]

Once all of these are done, you should be able to see your basic form in a test TOM:


|image0|

Customizing your Data Service:
******************************

The next step is to update our code to have all of the specific features relevant for our data service. Here we will focus on
extending several methods of ``DataService`` to perform the specific tasks needed to interface with your data service.
Ultimately there are many things that can be customized for your DataService, and many tools built into the base class
to help you do this. This section will take you through the fundamentals to get you started, but you should review the
:doc:`full class documentation <../api/tom_dataservices/data_services>` before you precede.


Filling out our ``MyServiceForm``
+++++++++++++++++++++++++++++++++
First, we will need actual fields in our Form. For more on this, see the `official Django
docs <https://docs.djangoproject.com/en/stable/topics/forms/>`__.


``DataService.build_query_parameters``
++++++++++++++++++++++++++++++++++++++++

Next, let's make our ``build_query_parameters`` function inside of ``MyDataService`` actually do something.
This code is to convert all of the form fields into a data dictionary or set of query parameters that is understood by
the data service (or more specifically our ``query_service`` method.)

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def build_query_parameters(self, parameters, **kwargs):
        """
        Use this function to convert the form results into the query parameters understood
        by the Data Service.
        """
        data = {
            'example_field': parameters.get('first_field')
        }

        self.query_parameters = data
        return data

In some cases, this can be very straightforward, while in others this can involve complex constructions of query
commands. Ultimately this is based on the API or client of your Data Service, and how you chose to name your form
fields.

``DataService.query_service``
+++++++++++++++++++++++++++++++

Next we will need to fill out our ``query_service`` module. This is the function that actually goes and calls the query
service using the parameters created by ``build_query_parameters``. This function produces query results that can then be
interpreted by ``query_targets``, ``query_photometry``, or other functions to produce specific kinds of results that can be
interpreted by your TOM.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def query_service(self, data, **kwargs):
            """
            This is where you actually make the call to the Data Service. 
            Return the results.
            """
            if self.get_urls(url_type='search'):
                results = requests.post(self.get_urls(url_type='search'), data, headers=self.build_headers())
            else:
                results = data_service_client.search(data)
            self.query_results = results
            return self.query_results

Again, depending on the nature of your data service, the ``query_service`` function could take many different forms.
This may also require you to create a ``build_headers`` method, or make use of the ``urls``, ``get_configuration``, or
``get_credentials`` methods. Saving the results to ``self.query_results`` could save time in other methods by not requiring
you to redo the query.

``DataService.query_targets``
++++++++++++++++++++++++++++++

We will just use ``query_targets`` as an example. The same ideas apply to any of the individual query functions.
This is the function that pulls useful data from the query results in a way that the TOM understands. In this case, we
will be extracting Target data from the query results and creating a list of dictionaries containing this target data.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def query_targets(self, query_parameters, **kwargs):
            """
            This code calls `query_service` and returns a list of dictionaries containing target results.
            This call and the results should be tailored towards describing targets.
            """
            # I can update my query parameters to include target specific information here if necessary
            query_results = self.query_service(query_parameters)
            targets = []
            for result in query_results:
                result['name'] = f"MyService:{result['ra']},{result['dec']}"
                targets.append(result)
            return targets # This should always be a list of dictionaries.

In this example, we create or modify the name of a query result so we will have something to enter into the TOM.
Line 6 calls the super which will either retrieve ``self.query_results`` if it exists or run ``query_service``.
The final output should be a list of dictionaries containing target results.

At this point you should be seeing a list of Targets showing up in your TOM after you perform a query.

``DataService.create_target_from_query``
++++++++++++++++++++++++++++++++++++++++++

Continuing with our ``target`` example, we need to be able to ``create_target_from_query`` in order to actually save the
target object resulting from a successful result for ``query_target`` above. This function expects a single instance with
the same format as the list of dictionaries created by ``query_targets`` and converts that dictionary into a Target Object
returning that object.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def create_target_from_query(self, target_result, **kwargs):
            """Create a new target from the query results
            :returns: target object
            :rtype: `Target`
            """

            target = Target(
                name=target_result['name'],
                type='SIDEREAL',
                ra=target_result['ra'],
                dec=target_result['dec']
            )
            return target


Integrating Additional Query Types:
***********************************

Above we discussed creating targets from queries, but usually the point of a query is to get data from a data service 
beyond the basic target information. This is where we need to build out methods like ``query_aliases`` and
``query_photometry``.

Each of these different kinds of data will require functions in ``MyDataService`` titled ``query_foo()`` and
``create_foo_from_query()``. These behave the same way as ``query_targets`` and ``create_target_from_query`` above, querying
the data service and returning a list of dictionaries in ``query_foo()``, and then translating an instance of that dictionary
into a model object with ``create_foo_from_query()``.

Depending on the specifics of your data service, it may be reasonable to call the ``query_foo()`` methods independently,
and/or part of ``query_targets``.

Querying Reduced Datums:
++++++++++++++++++++++++
Data from a dataservice that needs to be stored as a ``ReducedDatum`` should be handled a little differently.
The specifics of converting the query results into a list of dictionaries is handled by the ``query_foo()`` method for that
specific data type (i.e ``query_photometry()``). However, there are a few additional functions you will want to extend
when dealing with ``ReducedDatum``s. To do this generally, you may want to override or extend ``query_reduced_data()`` but
you can also do this for specific types of reduced data. In this section we will walk you through including photometry
data as an example.

We will start by creating our query:

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def query_photometry(self, query_parameters, **kwargs):
        """Set up and run a specialized query for a DataService’s photometry service.
        :returns: photometry_results
        :rtype: Usually a List of Dictionaries
        """
        query_parameters['return_lightcurve'] = True  # Modify query parameters if needed
        query_results = self.query_service(query_parameters)
        photometry_results = query_results['lightcurve']
        return photometry_results


``DataService.create_reduced_datums_from_query``
================================================

To create the ``ReducedDatum``s we will need a ``create_reduced_datums_from_query()`` method. This should take all of the data
types and convert them into ``ReducedDatum`` objects. Be sure to use ``ReducedDatum.objects.get_or_create()`` to prevent
re-creating existing objects.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def create_reduced_datums_from_query(self, target, data=None, data_type='photometry', **kwargs):
        """
        Create and save new reduced_datums of the appropriate data_type from the query results
        Be sure to use `ReducedDatum.objects.get_or_create()` when creating new objects.

        :param target: Target Object to be associated with the reduced data
        :param data: List of data dictionaries of the appropriate `data_type`
        :param data_type: An appropriate data type as listed in tom_dataproducts.models.DATA_TYPE_CHOICES
        :return: List of Reduced Datums (either retrieved or created)
        """
        reduced_datums = []
        for datum in data:
            datum_details = dict(datum)
            if data_type == 'photometry':
                # We might have some specific things we want to include based on type.
                # For Photometry, for example, we need a magnitude, error, and filter to be displayed in the
                # photometry plot on the target detail page.
                datum_details['magnitude'] = datum['my_mag']
                datum_details['error'] = datum['my_magerr']
                datum_details['limit'] = datum['my_maglim']
                datum_details['filter'] = datum['my_passband']

            reduced_datum, __ = ReducedDatum.objects.get_or_create(
                target=target,
                timestamp=Time(datum['time'], format='iso', scale='utc').datetime,
                data_type=data_type,
                source_name=self.name,
                value=datum_details
            )
            reduced_datums.append(reduced_datum)
        return reduced_datums


``DataService.build_query_parameters_from_target``
==================================================

It can be convenient to build a query just from a target object, as it already exists in the TOM. Thus, it can be
helpful to create a ``build_query_parameters_from_target()`` method. This method should take a target object, and return
query parameters that would be understood by your ``query_service()`` method. The TOMToolkit uses this method, if it
exists, in several places where we want to update an existing target based on data service data.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def build_query_parameters_from_target(self, target, **kwargs):
        """
        This is a method that builds query parameters based on an existing target object that will be recognized by
        `query_service()`.
        This can be done by either by re-creating the form fields we set in MyServiceForm and then calling
        `self.build_query_parameters()` with the results, or we can reproduce a limited set of parameters uniquely for
        a target query.

        :param target: A target object to be queried
        :return: query_parameters (usually a dict) that can be understood by `query_service()`
        """
            if 'first' in target.name:
                form_fields = {'first_field': target.name}
                query_parameters = self.build_query_parameters(form_fields)
            else:
                query_parameters= {
                    'ra_field': target.ra,
                    'dec_field': target.dec,
                    'radius': 0.5
                    }
            return query_parameters


Polishing Your Data Service:
****************************

At this point, you data service is functional, but may not look quite as nice as you would like in the browser.
In this section we will walk you through several important steps to customize the appearance of your dataservice.


Simple vs Advanced Forms:
+++++++++++++++++++++++++

For clarity it can be extremely useful to separate the base level functionality for a data service from the much more
complex features and search functionality that is possible with many catalogs, brokers, etc. Towards this end, the
TOMToolkit offers both simple and advanced forms for a dataservice. By default, an advanced Form will be collapsed
when a user first loads the form.

Simple Forms:
=============

Simple forms are often a single field that will find expected results. Such as a Target name or ID field.

This consists of adding the ``get_simple_form_partial()`` method to MyDataService and then creating the partial.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def get_simple_form_partial(self):
        """Returns a path to a simplified bare-minimum partial form that can be used to access the DataService."""
        return 'my_dataservice/partials/myservice_simple_form'


.. code-block:: html
    :caption: my_dataservice/partials/myservice_simple_form.html
    :linenos:

    {% load bootstrap4 %}
    {% bootstrap_field form.first_field %}

NOTES:
 - Here we are just rendering a single field from our form.

Advanced Forms:
===============

This is where we include all of the complex functionality that advanced users would need access to.
This can be handled in basically the same way as the simple form:

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def get_advanced_form_partial(self):
        """Returns a path to a simplified bare-minimum partial form that can be used to access the DataService."""
        return 'my_dataservice/partials/myservice_advanced_form'


.. code-block:: html
    :caption: my_dataservice/partials/myservice_advanced_form.html
    :linenos:

    {% load bootstrap4 %}
    {% bootstrap_form form exclude='query_name,query_save,first_field' %}

NOTES:

- Here we are rendering all the form fields except the one in the simple form and the 2 default fields that get displayed below.

Alternatively, if a simple form is included, the entirety of the form will be displayed by default in the advanced
section using whatever layout was provided. So you can easily use
`django_crispy_forms <https://django-crispy-forms.readthedocs.io/en/latest/index.html>`_ to set a layout instead of
creating a partial.

.. code-block:: python
    :caption: forms.py
    :linenos:

    from django import forms
    from tom_dataservices.forms import BaseQueryForm

    class MyServiceForm(BaseQueryForm):
        first_field = forms.CharField(required=False,
                                      label='An Example Field',
                                      help_text='Put important info here.')
        ra = forms.FloatField(required=False, min_value=0., max_value=360.,
                            label='R.A.',
                            help_text='Right ascension in degrees')
        dec = forms.FloatField(required=False, min_value=-90., max_value=90.,
                            label='Dec.',
                            help_text='Declination in degrees')
        radius = forms.FloatField(required=False, min_value=0.,
                            label='Cone Radius')

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.helper.layout = Layout(
                HTML('''
                    <p>
                    My Data Service can also do a cone Search!
                    </p>
                '''),
                Fieldset(
                    'Cone Search',
                    Div(
                        Div(
                            'ra',
                            'radius',
                            css_class='col',
                        ),
                        Div(
                            'dec',
                            'units',
                            css_class='col',
                        ),
                        css_class="form-row",
                    )
                ),


Target Results Table:
+++++++++++++++++++++

By default, all of your results except for ``reduced_datums`` will be displayed in the table. You may wish to customize
this display without compromising your results. You can do this by adding a ``query_results_table``. This is specialized
table partial for displaying query results for this data service. To implement this you should set the
``query_results_table`` value in your Data service pointed to the appropriate partial:

.. code-block:: python
    :caption: my_dataservice.py
    :linenos:

    from tom_dataservices.dataservices import DataService
    from my_dataservice.forms import MyServiceForm

    class MyDataService(DataService):
        """
        This is an Example Data Service with the minimum required
        functionality.
        """
        name = 'MyService'
        # The path to a specialized table partial for displaying query results
        query_results_table = 'my_dataservice/partials/myservice_query_results_table.html'

        ...


.. code-block:: html
    :caption: my_dataservice/partials/myservice_simple_form.html
    :linenos:

    <table class="table table-striped">
        <thead>
        <tr>
            <th><input type="checkbox" id="selectAll"/></th>
            <th>Name</th>
            <th>RA</th>
            <th>Dec</th>
        </tr>
        </thead>
        <tbody>
        {% for result in results %}
        <tr>
            <td><input type="checkbox" name="selected_results" value="{{ result.id }}"/></td>
            <td>{{ result.name}}</td>
            <td>{{ result.ra }}</td>
            <td>{{ result.dec }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>




.. |image0| image:: /_static/dataservices_doc/demo_Data_Service.png