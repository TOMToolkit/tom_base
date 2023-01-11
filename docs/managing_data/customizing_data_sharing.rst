Customizing Data Sharing
---------------------------

Currently, data sharing is only possible with HERMES.

You will need to add ``DATA_SHARING`` to your ``settings.py`` that will give the proper credentials for the various
streams, TOMS, etc. with which you desire to share data.

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
