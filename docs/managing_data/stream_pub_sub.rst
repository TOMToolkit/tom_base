Publish and Subscribe to a Kafka Stream
---------------------------------------

Publishing data to a stream and subscribing to a stream are handled independently and we describe each below.


Publish Data to a Kafka Topic
#############################

TOM Toolkit supports publishing data to a Kafka stream such as `Hermes <https://hermes.lco.global>`_ (an interface to
`HOPSKOTCH <https://hop.scimma.org>`_) and `GCNClassicOverKafka <https://gcn.nasa.gov>`_.

When sharing photometry data via Hermes, the TOM publishes the data to be shared to a topic on the HOPSKOTCH
Kafka stream. At this time, only photometry data is supported by TOM Toolkit. To submit via the Hermes API, you will
need to copy your Hermes API Key from your Hermes profile page. When hermes sharing is configured, you will also see
buttons to open your data in hermes with the form pre-filled - this is a good option if you want to make slight changes
to your message or data before sharing.


Configuring your TOM to Publish Data to a stream:
*************************************************

You will need to add a ``DATA_SHARING`` configuration dictionary to your ``settings.py`` that gives the credentials
for the various streams with which you wish to share data.

.. code:: python

   # Define the valid data sharing destinations for your TOM.
   DATA_SHARING = {
        'hermes': {
           'DISPLAY_NAME': os.getenv('HERMES_DISPLAY_NAME', 'Hermes'),
           'BASE_URL': os.getenv('HERMES_BASE_URL', 'https://hermes.lco.global/'),
           'HERMES_API_KEY': os.getenv('HERMES_API_KEY', 'set HERMES_API_KEY value in environment'),
           'DEFAULT_AUTHORS': os.getenv('HERMES_DEFAULT_AUTHORS', 'set your default authors here'),
           'USER_TOPICS': ['hermes.test', 'tomtoolkit.test']  # You must have write permissions on these topics
        },
   }

Subscribe to a Kafka Topic
##########################

TOM Toolkit allows a TOM to subscribe to a topic on a Kafka stream, ingesting messages from that topic and handling the data.
This could involve simply logging the message or extracting the data from the message and saving it if it is properly formatted.

Configuring your TOM to subscribe to a stream:
**********************************************

First you will need to add ``tom_alertstreams`` to your list of ``INSTALLED_APPS`` in your ``settings.py``.

.. code:: python

    INSTALLED_APPS = [
        ...
        'tom_alertstreams',
    ]

Then you will need to add an ``ALERT_STREAMS`` configuration dictionary to your ``settings.py``. This gives the credentials
for the various streams to which you wish to subscribe. Additionally, the ``TOPIC_HANDLERS`` section of the stream ``OPTIONS``
will include a list of handlers for each topic.

Some alert handlers are included as examples. Below we demonstrate how to connect to a Hermes Topic. You'll want to check
out the ``tom-alertstreams`` `README <https://github.com/TOMToolkit/tom-alertstreams>`_ for more details.

.. code:: python

    ALERT_STREAMS = [
        {
            'ACTIVE': True,
            'NAME': 'tom_alertstreams.alertstreams.hopskotch.HopskotchAlertStream',
            'OPTIONS': {
                'URL': 'kafka://kafka.scimma.org/',
                'USERNAME': os.getenv('SCIMMA_CREDENTIAL_USERNAME', 'set SCIMMA_CREDENTIAL_USERNAME value in environment'),
                'PASSWORD': os.getenv('SCIMMA_CREDENTIAL_PASSWORD', 'set SCIMMA_CREDENTIAL_USERNAME value in environment'),
                'TOPIC_HANDLERS': {
                    'tomtoolkit.test': 'tom_dataproducts.alertstreams.hermes.hermes_alert_handler',
                },
            },
        },
    ]
