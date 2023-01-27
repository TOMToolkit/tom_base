Sharing Data with Other TOMs
############################

TOM Toolkit does not yet support direct sharing between TOMs, however we hope to add this functionality soon.


..  Configuring your TOM to submit data to another TOM:
..  ***************************************************
..  
..  You will need to add a ``DATA_SHARING`` configuration dictionary to your ``settings.py`` that gives the credentials
..  for the various TOMs with which you wish to share data.
..  
..  .. code:: python
..  
..     # Define the valid data sharing destinations for your TOM.
..     DATA_SHARING = {
..          'tom-demo-dev': {
..              'DISPLAY_NAME': os.getenv('TOM_DEMO_DISPLAY_NAME', 'TOM Demo Dev'),
..              'BASE_URL': os.getenv('TOM_DEMO_BASE_URL', 'http://tom-demo-dev.lco.gtn/'),
..              'USERNAME': os.getenv('TOM_DEMO_USERNAME', 'set TOM_DEMO_USERNAME value in environment'),
..              'PASSWORD': os.getenv('TOM_DEMO_PASSWORD', 'set TOM_DEMO_PASSWORD value in environment'),
..          },
..          'localhost-tom': {
..              # for testing; share with yourself
..              'DISPLAY_NAME': os.getenv('LOCALHOST_TOM_DISPLAY_NAME', 'Local'),
..              'BASE_URL': os.getenv('LOCALHOST_TOM_BASE_URL', 'http://127.0.0.1:8000/'),
..              'USERNAME': os.getenv('LOCALHOST_TOM_USERNAME', 'set LOCALHOST_TOM_USERNAME value in environment'),
..              'PASSWORD': os.getenv('LOCALHOST_TOM_PASSWORD', 'set LOCALHOST_TOM_PASSWORD value in environment'),
..          }
..  
..     }
..  