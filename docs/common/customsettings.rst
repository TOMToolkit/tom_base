TOM Specific Settings
---------------------

The following is a list of TOM Specific settings to be added/edited in
your project’s ``settings.py``. For explanations of Django specific
settings, see the `official
documentation <https://docs.djangoproject.com/en/stable/ref/settings/>`__.

`AUTH_STRATEGY <#auth-strategy>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: ‘READ_ONLY’

Determines how your TOM treats unauthenticated users. A value of
**READ_ONLY** allows unauthenticated users to view most pages on your
TOM, but not to change anything. A value of **LOCKED** requires all
users to login before viewing any page. Use the
`OPEN_URLS <#open-urls>`__ setting for adding exemptions.

`DATA_PROCESSORS <#data-processors>`__
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

`DATA_PRODUCT_TYPES <#data-product-types>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

`EXTRA_FIELDS <#extra-fields>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: []

A list of extra fields to add to your targets. These can be used if the
predefined target fields do not match your needs. Please see the
documentation on :doc:`Adding Custom Fields to
Targets <../targets/target_fields>` for an explanation of how to use
this feature.

.. _custom_facility_settings:

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
documentation <https://docs.djangoproject.com/en/stable/ref/contrib/messages/#message-levels>`__.

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
such as an observation changing state. See the documentation on :doc:`Running
Custom Code on Actions in your TOM <../code/custom_code>` for more
details and available hooks.

`OPEN_URLS <#open-urls>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: []

With an `AUTH_STRATEGY <#auth-strategy>`__ value of **LOCKED**, urls in
this list will remain visible to unauthenticated users. You can also use wild cards to open an entire path.
You might add the homepage (‘/’), for example, or anything with a path that looks like ``'/accounts/reset/*/'``.

`TARGET_PERMISSIONS_ONLY <#target-permissions-only>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: True

This settings determines the permissions strategy of the TOM. When set
to True, authorization permissions will be set on Targets and cascade
from there–that is, a group that can see a Target can see all
ObservationRecords and Data associated with the Target. When set to
False, permissions can be set for a group at the Target level, the
ObservationRecord level, or the DataProduct level.

`TARGET_TYPE <#target-type>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: No default

Can be either **SIDEREAL** or **NON_SIDEREAL**. This setting determines
the default target type for your TOM. TOMs can still create and work
with targets of both types even after this option is set, but setting it
to one of the values will optimize the workflow for that target type.

`TARGET_LIST_COLUMNS <#target-list-columns>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block::

    ["name", "type", "observations", "saved_data"]

Display these columns in the target list table. Values can be attributes or properties on
the Target model, tags or extra fields. See :doc:`Customizing the Target List Table <../targets/target_table>`.

`TOM_FACILITY_CLASSES <#tom-facility-classes>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block

   [
      'tom_observations.facilities.lco.LCOFacility',
      'tom_observations.facilities.gemini.GEMFacility',
      'tom_observations.facilities.soar.SOARFacility',
      'tom_observations.facilities.blanco.BLANCOFacility',
      'tom_observations.facilities.lt.LTFacility'
   ]

A list of observation facility classes to make available to your TOM. If
you have written or downloaded a custom observation facility you would
add the class to this list to make your TOM load it.

`TOM_LATEX_PROCESSORS <#tom-latex-processors>`__
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

`TOM_REGISTRATION <#tom-registration>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

Example:

.. code-block

   {
      'REGISTRATION_AUTHENTICATION_BACKEND': 'django.contrib.auth.backends.ModelBackend',
      'REGISTRATION_REDIRECT_PATTERN': 'home',
      'SEND_APPROVAL_EMAILS': True
   }

`TOM_NAME <#tom-name>`__
~~~~~~~~~~~~~~~~~~~~~~~~

Default: TOM Toolkit

Set the name of the TOM, used for display purposes such as the navbar
and page titles.
