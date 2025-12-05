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

