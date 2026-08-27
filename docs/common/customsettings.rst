TOM Specific Settings
=====================

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
You might add the homepage (‘/’), for example, or an API path such as ``'/api/*'`` for scripts that authenticate
with a token. The login, sign-up, second-factor and password-reset pages are open automatically.

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

`TOM_ACCOUNT_REQUIREMENTS <#tom-account-requirements>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default:

.. code-block:: python

   [
       'tom_common.accounts.requirements.terms_of_service_accepted',
       'tom_common.accounts.requirements.mfa_enrolled',
       'tom_common.accounts.requirements.password_not_expired',
       'tom_common.accounts.requirements.required_fields_present',
   ]

Ordered list of checks applied to every request by a logged-in user. Each entry is the dotted path of a check
*function*; its companion ``TOM_*`` setting is the check's *parameter*. A check whose setting is left unconfigured
returns ``None`` immediately (no database queries), so the default list is entirely inactive out of the box:

.. list-table::
   :header-rows: 1
   :widths: 40 32 28

   * - Check function
     - Activated by configuring
     - Unsatisfied users are sent to
   * - ``terms_of_service_accepted``
     - ``TOM_TERMS_OF_SERVICE_VERSION``
     - the terms acceptance page
   * - ``mfa_enrolled``
     - ``TOM_MFA_REQUIRED``
     - two-factor enrolment
   * - ``password_not_expired``
     - ``TOM_PASSWORD_EXPIRY_DAYS``
     - the change-password page
   * - ``required_fields_present``
     - ``TOM_REQUIRED_USER_FIELDS``
     - their user edit page

The checks run on every request rather than only at login so that a change — a new terms-of-service version, a
password crossing its expiry age, an administrator removing a user's authenticator — takes effect during
long-lived sessions instead of at the next login. Every configured requirement also appears as a column on the
*Users* page so administrators can see who has not yet met it. Add your own check as a dotted path to a function
taking the request and returning ``None`` or the URL name of the page where the user can satisfy the requirement;
a custom check may read its own ``settings.py`` value following the same pattern. See
:doc:`Accounts and Authentication <authentication>`.

`TOM_API_TOKEN_EXPIRY_DAYS <#tom-api-token-expiry-days>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

When set to a number of days, API tokens older than that are rejected by ``tom_common.accounts.api_auth.TomTokenAuthentication``
and users must regenerate their token from their profile edit page.

`TOM_API_TOKEN_REQUIRES_MFA <#tom-api-token-requires-mfa>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: False

When ``True``, API tokens are only accepted for users who have enabled two-factor authentication (and only tokens
created after enrolment); the password-only ``/api/token-auth/`` endpoint is disabled and tokens can only be
regenerated by their owner after re-authenticating. Requires ``tom_common.accounts.api_auth.TomTokenAuthentication`` in
``REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`` — ``manage.py check`` warns (``tom_common.W001``) when either
token setting is configured without it.

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

INSTALLED_APPS that implement the ``observation_facilities()`` AppConfig integration
point do not need to be listed here.

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

`TOM_MFA_REQUIRED <#tom-mfa-required>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

``'all'`` requires every user (including superusers) to enroll an authenticator app before using the TOM;
``'superusers'`` requires it only for superusers. Two-factor authentication is always *available* to users; this
setting only makes it mandatory.

`TOM_NAME <#tom-name>`__
~~~~~~~~~~~~~~~~~~~~~~~~

Default: TOM Toolkit

Set the name of the TOM, used for display purposes such as the navbar
and page titles, and as the issuer shown in authenticator apps.

`TOM_PASSWORD_EXPIRY_DAYS <#tom-password-expiry-days>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

When set to a number of days, users whose password is older than that must change it before continuing. A password
set by an administrator counts as expired. Password *rules* are configured with Django's ``AUTH_PASSWORD_VALIDATORS``
(see :doc:`Accounts and Authentication <authentication>`).

`TOM_PASSWORD_RESET_ENABLED <#tom-password-reset-enabled>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: False

Enables password reset by email (``/accounts/password/reset/`` and a *Forgot your password?* link on the login
page). Requires a working ``EMAIL_BACKEND``.

`TOM_REGISTRATION <#tom-registration>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deprecated. This dictionary configured the ``tom_registration`` plugin; use ``TOM_REGISTRATION_STRATEGY`` instead
(see :doc:`Updating your TOM <../introduction/updating>`).

`TOM_REGISTRATION_STRATEGY <#tom-registration-strategy>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

``None``: only administrators create accounts. ``'open'``: visitors can sign up and are logged in immediately.
``'approval_required'``: visitors can sign up; the account stays inactive until a superuser approves it on the
*Users* page. New users join the ``Public`` group. Notification emails are sent when an email backend is configured.

`TOM_REQUIRED_USER_FIELDS <#tom-required-user-fields>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: []

Example: ``['first_name', 'last_name', 'email', 'affiliation', 'phone_number']``

Fields a user account must have. They are required on the sign-up and user edit forms, and a logged-in user with a
required field missing is taken to their edit page until it is filled in.

`TOM_TERMS_OF_SERVICE_VERSION <#tom-terms-of-service-version>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: None

Example: ``'2026-09-01'``

When set, users must accept the terms of service (the template ``tom_common/partials/terms_of_service_text.html``)
before using the TOM; acceptance of each version is recorded. Change the value to require re-acceptance.
