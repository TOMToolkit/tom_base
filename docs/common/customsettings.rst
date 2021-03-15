TOM Specific Settings
---------------------

The following is a list of TOM Specific settings to be added/edited in
your project’s ``settings.py``. For explanations of Django specific
settings, see the `official
documentation <https://docs.djangoproject.com/en/2.1/ref/settings/>`__.

`AUTH_STRATEGY <#auth_strategy>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: ‘READ_ONLY’

Determines how your TOM treats unauthenticated users. A value of
**READ_ONLY** allows unauthenticated users to view most pages on your
TOM, but not to change anything. A value of **LOCKED** requires all
users to login before viewing any page. Use the
`OPEN_URLS <#open_urls>`__ setting for adding exemptions.

`BROKERS <#brokers>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   {
        'TNS': {
           'api_key': ''
        },
        'SCIMMA': {
            'url': 'http://skip.dev.hop.scimma.org',
            'api_key': os.getenv('SKIP_API_KEY', ''),
            'hopskotch_url': 'dev.hop.scimma.org',
            'hopskotch_username': os.getenv('HOPSKOTCH_USERNAME', ''),
            'hopskotch_password': os.getenv('HOPSKOTCH_PASSWORD', ''),
            'default_hopskotch_topic': ''
        }
   }

Credentials and settings for any brokers that require them. At the moment, the only
built-in TOM Toolkit broker module that requires credentials is the TNS. SCIMMA and
ANTARES, which are available as add-on modules, also use this setting.

`DATA_PROCESSORS <#data_processors>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   {
       'photometry': 'tom_dataproducts.processors.photometry_processor.PhotometryProcessor',
       'spectroscopy': 'tom_dataproducts.processors.spectroscopy_processor.SpectroscopyProcessor',
   }

The ``DATA_PROCESSORS`` dict specifies the subclasses of
``DataProcessor`` that should be used for processing the corresponding
``data_type``\ s.

`DATA_PRODUCT_TYPES <#data_types>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   {
       'spectroscopy': ('spectroscopy', 'Spectroscopy'),
       'photometry': ('photometry', 'Photometry'),
       'spectroscopy': ('spectroscopy', 'Spectroscopy'),
       'image_file': ('image_file', 'Image File')
   }

A list of machine readable, human readable tuples which determine the
choices available to categorize reduced data.

`EXTRA_FIELDS <#extra_fields>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: []

A list of extra fields to add to your targets. These can be used if the
predefined target fields do not match your needs. Please see the
documentation on `Adding Custom Fields to
Targets </targets/target_fields>`__ for an explanation of how to use
this feature.

`FACILITIES <#facilities>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   {
       'LCO': {
           'portal_url': 'https://observe.lco.global',
           'api_key': os.getenv('LCO_API_KEY', ''),
       }
   }

Observation facilities read their configuration values from this
dictionary. Although each facility is different, if you plan on using
one you’ll probably have to configure it here first. For example the LCO
facility requires you to provide a value for the ``api_key``
configuration value.

`HARVESTERS <#harvesters>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   {
        'TNS': {
           'api_key': ''
        },
   }

Credentials and settings for any harvesters that require them. At the moment, the only
built-in TOM Toolkit broker module that requires credentials is the TNS.

`HINTS <#hints>`__
~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

    HINTS_ENABLED = False 
    HINT_LEVEL = 20

A few messages are sprinkled throughout the TOM Toolkit that offer
suggestions on things you might want to change right out of the gate.
These can be turned on and off, and the level adjusted. For more
information on Django message levels, see the `Django messages framework
documentation <https://docs.djangoproject.com/en/2.2/ref/contrib/messages/#message-levels>`__.

`HOOKS <#hooks>`__
~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   {
       'target_post_save': 'tom_common.hooks.target_post_save',
       'observation_change_state': 'tom_common.hooks.observation_change_state',
       'data_product_post_upload': 'tom_dataproducts.hooks.data_product_post_upload',
   }

A dictionary of action, method code hooks to run. These hooks allow
running arbitrary python code when specific actions happen within a TOM,
such as an observation changing state. See the documentation on `Running
Custom Code on Actions in your TOM </code/custom_code>`__ for more
details and available hooks.

`OPEN_URLS <#open_urls>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: []

With an `AUTH_STRATEGY <#auth_strategy>`__ value of **LOCKED**, urls in
this list will remain visible to unauthenticated users. You might add
the homepage (‘/’), for example.

`TARGET_PERMISSIONS_ONLY <#target_permissions_only>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: True

This settings determines the permissions strategy of the TOM. When set
to True, authorization permissions will be set on Targets and cascade
from there–that is, a group that can see a Target can see all
ObservationRecords and Data associated with the Target. When set to
False, permissions can be set for a group at the Target level, the
ObservationRecord level, or the DataProduct level.

`TARGET_TYPE <#target_type>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: No default

Can be either **SIDEREAL** or **NON_SIDEREAL**. This setting determines
the default target type for your TOM. TOMs can still create and work
with targets of both types even after this option is set, but setting it
to one of the values will optimize the workflow for that target type.

`TOM_ALERT_CLASSES <#tom_alert_classes>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

   [
       'tom_alerts.brokers.mars.MARSBroker',
       'tom_alerts.brokers.lasair.LasairBroker',
       'tom_alerts.brokers.scout.ScoutBroker',
       'tom_alerts.brokers.tns.TNSBroker',
       'tom_alerts.brokers.antares.ANTARESBroker',
       'tom_alerts.brokers.gaia.GaiaBroker'
   ]

A list of tom alert classes to make available to your TOM. If you have
written or downloaded additional alert classes you would make them
available here. If you’d like to write your own alert module please see
the documentation on `Creating an Alert Module for the TOM
Toolkit </brokers/create_broker>`__.

`TOM_ALERT_DASH_CLASSES <#tom_alert_dash_classes>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block:: python

   [
      'tom_alerts_dash.brokers.alerce.ALeRCEDashBroker',
      'tom_alerts_dash.brokers.mars.MARSDashBroker',
   ]

A list of tom alert dash classes to make available to your TOM. If you have
written or downloaded additional alert classes you would make them
available here. If you’d like to write your own dash alert module, please see
the documentation on `Plotly Dash Broker Modules in the TOM Toolkit </brokers/create_dash_broker>`__.

`TOM_FACILITY_CLASSES <#tom_facility_classes>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block

   [
      'tom_observations.facilities.lco.LCOFacility',
      'tom_observations.facilities.gemini.GEMFacility',
      'tom_observations.facilities.soar.SOARFacility',
      'tom_observations.facilities.lt.LTFacility'
   ]

A list of observation facility classes to make available to your TOM. If
you have written or downloaded a custom observation facility you would
add the class to this list to make your TOM load it.

`TOM_HARVESTER_CLASSES <#tom_harvester_classes>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block

   [
       'tom_catalogs.harvesters.simbad.SimbadHarvester',
       'tom_catalogs.harvesters.ned.NEDHarvester',
       'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
       'tom_catalogs.harvesters.mpc.MPCHarvester',
       'tom_catalogs.harvesters.tns.TNSHarvester',
   ]

A list of TOM harverster classes to make available to your TOM. If you
have written or downloaded additional harvester classes you would make
them available here.

`TOM_LATEX_PROCESSORS <#tom_latex_processors>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block

   {
       'ObservationGroup': 'tom_publications.processors.latex_processor.ObservationGroupLatexProcessor',
       'TargetList': 'tom_publications.processors.target_list_latex_processor.TargetListLatexProcessor'
   }

A dictionary with the keys being TOM models classes and the values being
the modules that should be used to generate latex tables for those
models.

`TOM_REGISTRATION <#tom_registration>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

Example:

.. code-block

   {
      'REGISTRATION_AUTHENTICATION_BACKEND': 'django.contrib.auth.backends.ModelBackend',
      'REGISTRATION_REDIRECT_PATTERN': 'home',
      'SEND_APPROVAL_EMAILS': True
   }
