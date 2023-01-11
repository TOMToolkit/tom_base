Sharing Data with Other TOMs
############################

TOM Toolkit supports data sharing in two ways: sharing data directly from one TOM Toolkit-based TOM to another and
sharing data between TOMs via `Hermes <https://hermes.lco.global>`_, an interface to `HOPSKOTCH <https://hop.scimma.org>`_,
a Kafka stream dedicated to Astronomical messaging. (Learn more about HOPSKOTCH and Hermes by following those links).

Currently, data sharing is only possible with Hermes. Sharing data directly between two TOM Toolkit-based TOMs will be
avalable soon.

When sharing data between TOMs via Hermes, the source TOM publishes the data to shared to a topic on the HOPSKOTCH
Kafka stream. The TOM receiving the data subscribes to the topic on the Kafka stream, ingesting messages on topic,
extracting the data from the message, and saving it. So, publishing (sending) and subscribing (receiving) data are
handled separately.


Configuring your TOM to Send Data
*********************************

You will need to add a ``DATA_SHARING`` configuration dictionary to your ``settings.py`` that gives the credentials
for the various streams, TOMS, etc. with which you wish to share data.

.. code:: python

   # Define the valid data sharing destinations for your TOM.
   DATA_SHARING = {
        'hermes': {
           'DISPLAY_NAME': os.getenv('HERMES_DISPLAY_NAME', 'Hermes'),
           'BASE_URL': os.getenv('HERMES_BASE_URL', 'https://hermes.lco.global/'),
           'CREDENTIAL_USERNAME': os.getenv('SCIMMA_CREDENTIAL_USERNAME',
                                             'set SCIMMA_CREDENTIAL_USERNAME value in environment'),
           'CREDENTIAL_PASSWORD': os.getenv('SCIMMA_CREDENTIAL_PASSWORD',
                                             'set SCIMMA_CREDENTIAL_PASSWORD value in environment'),
           'USER_TOPICS': ['hermes.test', 'tomtoolkit.test']
        },
        'tom-demo-dev': {
            'DISPLAY_NAME': os.getenv('TOM_DEMO_DISPLAY_NAME', 'TOM Demo Dev'),
            'BASE_URL': os.getenv('TOM_DEMO_BASE_URL', 'http://tom-demo-dev.lco.gtn/'),
            'USERNAME': os.getenv('TOM_DEMO_USERNAME', 'set TOM_DEMO_USERNAME value in environment'),
            'PASSWORD': os.getenv('TOM_DEMO_PASSWORD', 'set TOM_DEMO_PASSWORD value in environment'),
        },
        'localhost-tom': {
            # for testing; share with yourself
            'DISPLAY_NAME': os.getenv('LOCALHOST_TOM_DISPLAY_NAME', 'Local'),
            'BASE_URL': os.getenv('LOCALHOST_TOM_BASE_URL', 'http://127.0.0.1:8000/'),
            'USERNAME': os.getenv('LOCALHOST_TOM_USERNAME', 'set LOCALHOST_TOM_USERNAME value in environment'),
            'PASSWORD': os.getenv('LOCALHOST_TOM_PASSWORD', 'set LOCALHOST_TOM_PASSWORD value in environment'),
        }

   }
