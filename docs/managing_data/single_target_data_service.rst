Integrating Single-Target Data Service Queries
----------------------------------------------

The base TOM Toolkit comes with `ATLAS <https://fallingstar-data.com/forcedphot/>`__,
`PanSTARRS <https://outerspace.stsci.edu/display/PANSTARRS>`__,
and (coming soon) ZTF query services. These services query a specific catalog to return data for an
individual target and are optional, requiring additional configuration in order to integrate into your TOM.

Additional services can be added by extending the ``BaseSingleTargetDataService`` implementation
(:ref:`see below<Adding a new Single-Target Data Service>`).


Integrating existing Single-Target Data Services
################################################

You must add certain configuration to your TOM's ``settings.py`` to setup the existing single-target data
services. This configuration will go in the ``SINGLE_TARGET_DATA_SERVICES`` section
shown below:

.. code:: python

    SINGLE_TARGET_DATA_SERVICES = {
        'ATLAS': {
            'class': 'tom_dataproducts.single_target_data_service.atlas.AtlasForcedPhotometryService',
            'url': "https://fallingstar-data.com/forcedphot",
            'api_key': os.getenv('ATLAS_FORCED_PHOTOMETRY_API_KEY', 'your atlas account api token')
        },
        'PANSTARRS': {
            'class': 'tom_dataproducts.single_target_data_service.panstarrs_service.panstarrs.PanstarrsSingleTargetDataService',
            'url': 'https://catalogs.mast.stsci.edu/api/v0.1/panstarrs',  # MAST Base URL
            # MAST_API_TOKEN is not required for public data
            'api_key': os.getenv('MAST_API_TOKEN', 'MAST_API_TOKEN not set')
        },
        # TODO: coming soon...
        #     # 'ZTF': {
        # }
    }

    DATA_PRODUCT_TYPES = {
        ...
        'atlas_photometry': ('atlas_photometry', 'Atlas Photometry'),
        'panstarrs_photometry': ('panstarrs_photometry', 'PanSTARRS Photometry'),
        ...
    }

    DATA_PROCESSORS = {
        ...
        'atlas_photometry': 'tom_dataproducts.processors.atlas_processor.AtlasProcessor',
        'panstarrs_photometry': 'tom_dataproducts.processors.panstarrs_processor.PanstarrsProcessor',
        ...
    }

As you can see in the ``SINGLE_TARGET_DATA_SERVICES`` configuration dictionary above, some services require an API key.
Information on how to obtain an API key is available for both for `ATLAS <https://fallingstar-data.com/forcedphot/apiguide/>`_
and for `PanSTARRS <https://auth.mast.stsci.edu/info>`_. (PanSTARRS Photometry is accessed via `Catalogs.MAST <https://catalogs.mast.stsci.edu/>`_).

Configuring your TOM to serve tasks asynchronously:
***************************************************

Several of the services are best suited to be queried asynchronously, especially if you plan to make large
queries that would take a long time. The TOM Toolkit can be setup to use `dramatiq <https://dramatiq.io/index.html>`_
as an asynchronous task manager, and doing so requires you to run either a `redis <https://github.com/redis/redis>`_
or `rabbitmq <https://github.com/rabbitmq/rabbitmq-server>`_ server to act as the task queue. To use dramatiq with
a redis server, you would add the following to your ``settings.py``:

.. code:: python

    INSTALLED_APPS = [
        ...
        'django_dramatiq',
        ...
    ]

    DRAMATIQ_BROKER = {
        "BROKER": "dramatiq.brokers.redis.RedisBroker",
        "OPTIONS": {
            "url": "redis://your-redis-service-url:your-redis-port"
        },
        "MIDDLEWARE": [
            "dramatiq.middleware.AgeLimit",
            "dramatiq.middleware.TimeLimit",
            "dramatiq.middleware.Callbacks",
            "dramatiq.middleware.Retries",
            "django_dramatiq.middleware.DbConnectionsMiddleware",
        ]
    }

After adding the ``django_dramatiq`` installed app, you will need to run ``./manage.py migrate`` once to setup
its DB tables. If this configuration is set in your TOM, the existing services which support asynchronous queries,
Atlas and ZTF, should start querying asynchronously. (Note: You must also start the dramatiq workers:
``./manage.py rundramatic``. If you do not add these settings, those services will still function but will fall
back to synchronous queries.


Adding a new Single-Target Data Service
#######################################

The Single-Target Data services fulfill an interface defined in
`BaseSingleTargetDataService <https://github.com/TOMToolkit/tom_base/blob/dev/tom_dataproducts/single_target_data_service/single_target_data_service.py>`_.
To implement your own single-target data service, you need to do three things:

#. Subclass ``BaseSingleTargetDataService``
#. Subclass ``BaseSingleTargetDataServiceQueryForm``
#. Subclass ``DataProcessor``

Once those subclasses are implemented, don't forget to update your settings for ``SINGLE_TARGET_DATA_SERVICES``,
``DATA_PRODUCT_TYPES``, and ``DATA_PROCESSORS`` for your new service and its associated data product type.


Subclass BaseSingleTargetDataService:
*************************************

The most important method here is the ``query_service`` method which is where you put your service's business logic
for making the query, given the form parameters and target. This method is expected to create a DataProduct in the database
at the end of the query, storing the result file or files. If queries to your service are expected to take a long time and
you would like to make them asynchronously (not blocking the UI while calling), then follow the example in the
`atlas implementation <https://github.com/TOMToolkit/tom_base/blob/dev/tom_dataproducts/single_target_data_service/atlas.py>`_ and place your
actual asynchronous query method in your module's ``tasks.py`` file so it can be found by dramatiq. Like in the atlas implementation,
your code should check to see if ``django_dramatiq`` is in the settings ``INSTALLED_APPS`` before trying to enqueue it with dramatiq.

The ``get_data_product_type`` method should return the name of your new data product type you are going to define a
DataProcessor for. This must match the name you add to ``DATA_PROCESSORS`` and ``DATA_PRODUCT_TYPES`` in your ``settings.py``.
You will also need to define a
`DataProcessor <https://github.com/TOMToolkit/tom_base/blob/dev/tom_dataproducts/data_processor.py#L46>`_
for this data type. 


Subclass BaseSingleTargetDataServiceQueryForm:
**********************************************

This class defines the form users will need to fill out to query the service. It uses
`django-crispy-forms <https://django-crispy-forms.readthedocs.io/en/latest/>`_ to define the layout
programmatically. You first will add whatever form fields you need to the base of your
subclass, and then just fill in the ``layout()`` method with a django-crispy-forms layout
for your fields, and optionally the ``clean()`` method if you want to perform any field validation.
The values of the fields from this form will be available to you in your service class in the
``query_service`` method.


Subclass DataProcessor:
***********************

You must create a custom DataProcessor that knows how to convert data returned from your service into
a series of either photometry or spectroscopy datums. Without defining this step, your queries will still
result in a DataProduct file being stored from the service's ``query_service`` method, but those files will
not be parsed into photometry or spectroscopy datums. You can read more about how to implement a custom 
DataProcessor `here <./customizing_data_processing.html>`_.