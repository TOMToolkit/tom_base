Sharing Data with Other TOMs
############################

TOM Toolkit supports direct data sharing between TOMs.


Permissions:
************
To save data to a destination TOM your TOM will need to have access to a user account on that TOM with the correct
permissions. This is handled by your TOM's administrator as described below.

.. warning:: Any user who has permission to access the relevant target or data in your TOM will have permission to
            submit that data to the destination TOM once DATA_SHARING is configured.


Configuring your TOM to submit data to another TOM:
***************************************************

You will need to add a ``DATA_SHARING`` configuration dictionary to your ``settings.py`` that gives the credentials
for the various TOMs with which you wish to share data. This should be the same ``DATA_SHARING`` dictionary that is used
to :doc:`/managing_data/stream_pub_sub` such as `Hermes <https://hermes.lco.global>`_.

.. code:: python

    # Define the valid data sharing destinations for your TOM.
    DATA_SHARING = {
        'not-my-tom': {
            # For sharing data with another TOM
            'DISPLAY_NAME': os.getenv('NOT_MY_TOM_DISPLAY_NAME', 'Not My Tom'),
            'BASE_URL': os.getenv('NOT_MY_TOM_BASE_URL', 'http://notmytom.com/'),
            'USERNAME': os.getenv('NOT_MY_TOM_USERNAME', 'set NOT_MY_TOM_USERNAME value in environment'),
            'PASSWORD': os.getenv('NOT_MY_TOM_PASSWORD', 'set NOT_MY_TOM_PASSWORD value in environment'),
        },
        'localhost-tom': {
            # for testing; share with yourself
            'DISPLAY_NAME': os.getenv('LOCALHOST_TOM_DISPLAY_NAME', 'Local'),
            'BASE_URL': os.getenv('LOCALHOST_TOM_BASE_URL', 'http://127.0.0.1:8000/'),
            'USERNAME': os.getenv('LOCALHOST_TOM_USERNAME', 'set LOCALHOST_TOM_USERNAME value in environment'),
            'PASSWORD': os.getenv('LOCALHOST_TOM_PASSWORD', 'set LOCALHOST_TOM_PASSWORD value in environment'),
        }
    }

Receiving Shared Data:
**********************

Reduced Datums:
---------------
When your TOM receives a new ``ReducedDatum`` from another TOM it will be saved to your TOM's database with its source
set to the name of the TOM that submitted it. Currently, only Photometry data can be directly shared between
TOMS and a ``Target`` with a matching name or alias must exist in both TOMS for sharing to take place.

Data Products:
--------------
When your TOM receives a new ``DataProduct`` from another TOM it will be saved to your TOM's database / storage and run
through the appropriate :doc:`data_processor </managing_data/customizing_data_processing>` pipeline. Only data products
associated with a ``Target`` with a name or alias that matches that of a target in the destination TOM will be shared.

Targets:
--------
When your TOM receives a new ``Target`` from another TOM it will be saved to your TOM's database. If the target's name
or alias doesn't match that of a target that already exists in the database, a new target will be created and added to a
new ``TargetList`` called "Imported from <TOM Name>".

Target Lists:
-------------
When your TOM receives a new ``TargetList`` from another TOM it will be saved to your TOM's database. If the targets in
the ``TargetList`` are also shared, but already exist in the destination TOM, they will be added to the new
``TargetList``.






