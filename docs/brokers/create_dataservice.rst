Adding a Data Service Module for the TOM Toolkit
------------------------------------------------

This guide is to walk you step by step through the process of creating a Data Service.
This assumes that you want a user interface for querying your data service via a form.
Many of these steps can be skipped if your service is only intended to be accessed internally.

Setting up the Basic Data Service:
**********************************

First we will build the bare bones of our data service. This is the bare minimum to get the service to show up in the 
TOM. We'll start with three peices of code:

First the actual query class:
+++++++++++++++++++++++++++++


.. code-block:: python
    :caption: my_dataservice.py
    :linenos:

    from tom_dataservices.dataservices import BaseDataService
    from my_dataservice.forms import MyServiceForm

    class MyDataService(BaseDataService):
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


Customizing your Data Service:
******************************

The next step is to update our code to have all specific features relevent for our data service. Here we will focus on
extending several methods of `BaseDataService` to be relevent for your data service.


`BaseDataService.build_query_parameters`
++++++++++++++++++++++++++++++++++++++++

For starters, let's make our `build_query_parameters` function inside of `MyDataService` actually do something.
This code is to convert all of the form fields into a data dictionary or set of query parameters that is understood by
the data service (or more specifically our `query_service` method.)

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

`BaseDataService.query_service`
+++++++++++++++++++++++++++++++

Next we will need to fill out our `query_service` module. This is the function that actualy goes and calls the query
service using the parameters created by `build_query_parameters`. This function produces query results that can then be
interpreted by `query_targets`, `query_photometry`, or other functions to produce specific kinds of results that can be 
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

Again, depending on the nature of your data service, the `query_service` function could take many different forms. 
This may also require you to create a `build_headers` method, or make use of the `urls`, `get_configuration`, or 
`get_credentials`methods. Saving the results to `self.query_results` could save time in other methods by not requireing 
you to redo the query.

`BaseDataService.query_target`
++++++++++++++++++++++++++++++

We will just use `query_target` as an example. The same ideas apply to any of the individual query functions.
This is the function that pulls useful data from the query results in a way that the TOM understands. In this case, we 
will be extracting Target data from the query results and creating a dictionary.

.. code-block:: python
    :caption: my_dataservice.MyDataService
    :linenos:

    def query_target(self, data, **kwargs):
            """
            This code calls `query_dataservice` and returns a dictionary of results.
            This call and the results should be tailroed towards describing targets.
            """
            query_results = super().query_targets(data)
            targets = []
            for result in query_results:
                result['name'] = f"MyService:{result['ra']},{result['dec']}"
                targets.append(result)
            return targets

In this example, we create or modify the name of a query result so we will have something to enter into the TOM.
Line 6 calls the super which will either retrieve `self.query_results` if it exists or run `query_service`. 
The final output should be a dictionary of results.

`BaseDataService.create_target_from_query`
++++++++++++++++++++++++++++++++++++++++++

Continuing with our `target` example, we need to be able to `create_target_from_query` in order to actually save the
target object resulting from a succesful result for `query_target` above. This function expects a single instance with
the same format as the list of dictionaries created by `query_targets` and converts that dictionary into a Target Object
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