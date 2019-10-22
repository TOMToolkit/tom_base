TOM Specific Settings
---------------------

The following is a list of TOM Specific settings to be added/edited in your
project's `settings.py`. For explanations of Django specific settings, see the
[official documentation](https://docs.djangoproject.com/en/2.1/ref/settings/).

### [AUTH_STRATEGY](#auth_strategy)

Default: 'READ_ONLY'

Determines how your TOM treats unauthenticated users. A value of **READ_ONLY**
allows unauthenticated users to view most pages on your TOM, but not to change
anything. A value of **LOCKED** requires all users to login before viewing any
page. Use the [**OPEN_URLS**](#open_urls) setting for adding exemptions.


### [DATA_PRODUCT_TYPES](#data_types)

Default:

    {
        'spectroscopy': ('spectroscopy', 'Spectroscopy'),
        'photometry': ('photometry', 'Photometry')
    }

A list of machine readable, human readable tuples which determine the choices
available to categorize reduced data.


### [EXTRA_FIELDS](#extra_fields)

Default: []

A list of extra fields to add to your targets. These can be used if the predefined
target fields do not match your needs. Please see the documentation on [Adding
Custom Fields to Targets](/customization/target_fields) for an explanation of how to use
this feature.


### [FACILITIES](#facilities)

Default:

    {
        'LCO': {
            'portal_url': 'https://observe.lco.global',
            'api_key': os.getenv('LCO_API_KEY', ''),
        }
    }

Observation facilities read their configuration values from this dictionary.
Although each facility is different, if you plan on using one you'll probably have
to configure it here first. For example the LCO facility requires you to provide a
value for the `api_key` configuration value.


### [HINTS](#hints)

Default:

HINTS_ENABLED = False
HINT_LEVEL = 20

A few messages are sprinkled throughout the TOM Toolkit that offer suggestions on
things you might want to change right out of the gate. These can be turned on and
off, and the level adjusted. For more information on Django message levels, see
the [Django messages framework documentation](https://docs.djangoproject.com/en/2.2/ref/contrib/messages/#message-levels).


### [HOOKS](#hooks)

Default:

    {
        'target_post_save': 'tom_common.hooks.target_post_save',
        'observation_change_state': 'tom_common.hooks.observation_change_state',
        'data_product_post_upload': 'tom_dataproducts.hooks.data_product_post_upload',
    }

A dictionary of action, method code hooks to run. These hooks allow running
arbitrary python code when specific actions happen within a TOM, such as an
observation changing state. See the documentation on [Running Custom Code on
Actions in your TOM](/advanced/custom_code) for more details and available hooks.


### [OPEN_URLS](#open_urls)

Default: []

With an [**AUTH_STRATEGY**](#auth_strategy) value of **LOCKED**, urls in this list will remain
visible to unauthenticated users. You might add the homepage ('/'), for example.


### [TARGET_TYPE](#target_type)

Default: No default

Can be either **SIDEREAL** or **NON_SIDEREAL**. This settings determines the
default target type for your TOM. TOMs can still create and work with targets of
both types even after this option is set, but setting it to one of the values will
optimize the workflow for that target type.


### [TOM_ALERT_CLASSES](#tom_alert_classes)

Default:

    [
        'tom_alerts.brokers.mars.MARSBroker',
        'tom_alerts.brokers.lasair.LasairBroker',
        'tom_alerts.brokers.scout.ScoutBroker'
    ]

A list of tom alert classes to make available to your TOM. If you have written or
downloaded additional alert classes you would make them available here. If you'd
like to write your own alert module please see the documentation on [Creating an
Alert Module for the TOM Toolkit](/customization/create_broker).


### [TOM_FACILITY_CLASSES](#tom_facility_classes)

Default:

    [
        'tom_observations.facilities.lco.LCOFacility',
        'tom_observations.facilities.gemini.GEMFacility',
    ]

A list of observation facility classes to make available to your TOM. If you have
written or downloaded a custom observation facility you would add the class to
this list to make your TOM load it.


### [TOM_HARVESTER_CLASSES](#tom_harvester_classes)

Default:

    [
        'tom_catalogs.harvesters.simbad.SimbadHarvester',
        'tom_catalogs.harvesters.ned.NEDHarvester',
        'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
        'tom_catalogs.harvesters.mpc.MPCHarvester',
        'tom_catalogs.harvesters.tns.TNSHarvester',
    ]

A list of TOM harverster classes to make available to your TOM. If you have
written or downloaded additional harvester classes you would make them available
here.
