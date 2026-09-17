Updating your TOM
=================

Keep your TOM up to date by regularly installing the most recent version of the tomtoolkit and its associated apps from
PyPI. How exactly you do this (`pip`, `uv`, etc) will change based on how you handle dependencies for your project.


Upgrade to TOM Toolkit 3.1 (accounts and authentication)
--------------------------------------------------------

TOM Toolkit version 3.1 adds optional two-factor authentication, self-registration,
password policy/expiry, terms-of-service acceptance, mandatory profile fields,
API-token controls, and other features by integrating
`django-allauth <https://docs.allauth.org/en/latest/>`_.
**django-allauth** is the de-facto standard Django package for login, registration,
password management and multi-factor authentication. The new capabilities are turned off
by default so your TOM's behavior won't change without you configuring it to change.
The available new features are described in :doc:`Accounts and Authentication <../common/authentication>`.
This section is about how to upgrade an existing TOM.

If your TOM is still on TOM Toolkit v2, do the :ref:`v2 to v3 steps <upgrade-v2-v3>` first,
then come back here.

1.) Updating dependencies (``pyproject.toml``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bump ``tomtoolkit`` to ``>=3.1,<4`` and, if you use it, **remove** ``tom_registration`` from your dependencies.
Its two registration workflows are now part of tom_base (see step 5 below). (``django-allauth`` is installed
as a dependency of tomtoolkit. So, you don't list it in your dependencies).
If your TOM already uses ``django-allauth`` (e.g. for social login), make sure your own version constraint
allows the version tomtoolkit requires (``django-allauth[mfa] >=65.19.1,<66``).

2.) Updating ``settings.py``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. Note::
    This step assumes your ``settings.py`` uses ``from tom_common.default_settings import *``.
    If yours doesn't, please follow :ref:`step 4 of the v2→v3 upgrade <upgrade-v2-v3-settings>`
    instructions below. TOM Toolkit 3.1's new apps, middleware, and authentication backends are
    delivered through this mechanism.

``AUTHENTICATION_BACKENDS`` now follows the same pattern as ``INSTALLED_APPS`` and ``MIDDLEWARE``.
So, if in your ``settings.py``, you define your own ``AUTHENTICATION_BACKENDS``, replace it
with the concatenated list below::

    AUTHENTICATION_BACKENDS = TOMTOOLKIT_AUTHENTICATION_BACKENDS + [<your authentication backends here>]

3.) Back up and migrate your database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. Warning::

    django-allauth's migrations **lower-case every user's email address**. If you have users whose emails differ only
    by case, decide which should survive before migrating. Back up your database first.

::

   ./manage.py migrate

This creates the django-allauth tables (``account_emailaddress``, ``account_emailconfirmation``,
``mfa_authenticator``). We've added some new fields to the user profile. They are optional
unless configured otherwise (see :ref:`profile fields <auth-profile-fields>`).

4.) Check your templates and custom code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Login and logout URL names**. The URL names that django-allauth uses for login and logout pages are
  ``account_login`` / ``account_logout``. The Django URL names (``login`` and ``logout``) and their paths
  (``/accounts/login/`` and ``/accounts/logout/``, respectively) are retained for backward compatibility only.
  So, while technically no changes are required, new code should use ``account_login`` / ``account_logout``
  and existing templates could (perhaps should) be updated to do the same.

- **Login page template**. The login page template is now django-allauth's ``account/login.html``.
  The old login page template was ``registration/login.html``, which no longer renders. If your TOM
  overrides the old template (``registration/login.html``), copy django-allauth's ``account/login.html``
  into your project's ``templates/account/login.html`` and add your customizations there.

- **URL paths in urls.py**. If your ``urls.py`` defines its own ``accounts/login/`` or ``accounts/logout/``
  route, or includes ``django.contrib.auth.urls`` at ``accounts/``, remove those ``urlpatterns``. They
  would bypass the new login (and two-factor authentication). ``manage.py check`` reports this as::

      (tom_common.W003) LOGIN_URL (/accounts/login/) is served by django.contrib.auth.views.LoginView,
      not by django-allauth — logging in there bypasses the two-factor authentication challenge.

- **Copied tom_common templates**. If your TOM has its own copy of one of these templates, integrate your
  customizations with a copy from the new tom_base version:

  - ``auth/user_list.html`` and ``auth/partials/user_list.html``: these add the two-factor and
    account-requirement columns to the User list page and make the Email column visible only to superusers.
  - ``tom_common/base.html``: the new ``content_container`` block centers allauth's account pages.

5.) Replace ``tom_registration``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``tom_registration`` plugin is deprecated: its final release only prints a deprecation warning, and tom_base
warns at startup while it is installed. Its two flows are built in:

.. list-table::
    :header-rows: 1
    :widths: 50 50

    * - ``tom_registration``
      - tom_base 3.1
    * - ``'tom_registration'`` in ``INSTALLED_APPS``
      - remove
    * - ``tom_registration.middleware.RedirectAuthenticatedUsersFromRegisterMiddleware``
      - remove
    * - ``TOM_REGISTRATION = {'REGISTRATION_STRATEGY': 'open', ...}``
      - ``TOM_REGISTRATION_STRATEGY = 'open'``
    * - ``TOM_REGISTRATION = {'REGISTRATION_STRATEGY': 'approval_required', ...}``
      - ``TOM_REGISTRATION_STRATEGY = 'approval_required'``
    * - ``REGISTRATION_AUTHENTICATION_BACKEND``
      - not needed
    * - ``REGISTRATION_REDIRECT_PATTERN``
      - ``LOGIN_REDIRECT_URL`` / ``ACCOUNT_SIGNUP_REDIRECT_URL``
    * - ``SEND_APPROVAL_EMAILS``, ``APPROVAL_SUBJECT``, ``APPROVAL_MESSAGE``
      - emails are sent whenever an email backend is configured; customise the
        ``account/email/registration_*`` templates
    * - ``AllowAllUsersModelBackend`` in ``AUTHENTICATION_BACKENDS``
      - replace with the backends in step 2
    * - ``OPEN_URLS = ['/accounts/register/']`` (``LOCKED`` TOMs)
      - not needed (sign-up pages are open automatically)
    * - ``templates/tom_registration/register_user.html``
      - ``templates/account/signup.html``
    * - ``templates/tom_registration/partials/pending_users.html``
      - ``templates/auth/partials/pending_users.html``
    * - ``{% url 'registration:register' %}`` / ``{% url 'registration:approve' pk %}``
      - ``{% url 'account_signup' %}`` / ``{% url 'user-approve' pk %}``
    * - subclasses of its views and forms
      - ``ACCOUNT_SIGNUP_FORM_CLASS`` / ``ACCOUNT_ADAPTER`` (see :doc:`Accounts and Authentication <../common/authentication>`)

Pending (not yet approved) users are still simply inactive users; existing pending accounts appear in the new
*Pending users* table without any data migration.

Two copied templates matter to registration specifically. If your TOM has its own copy of
``tom_common/partials/navbar_login.html``, refresh it from the current tom_base version to get the *Register*
button (shown while self-registration is open). If it has its own copy of ``auth/user_list.html``, refresh
that too: the *Pending users* table renders from there.

6.) New default behaviour to be aware of
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Failed logins are rate-limited (5 per username per 5 minutes, plus per-IP limits) using Django's cache. Multi-host
  deployments should use a shared cache; TOMs behind a proxy should set ``ALLAUTH_TRUSTED_PROXY_COUNT``. See
  :ref:`auth-deployment-notes`.
- Two-factor authentication is *available* to every user (optional). Security-sensitive pages ask users to confirm
  their password again if they logged in more than a few minutes ago.
- With ``AUTH_STRATEGY = 'LOCKED'``, the login, sign-up, second-factor and pending-approval pages are open without
  listing them in ``OPEN_URLS``; ``/api/`` paths used with tokens still need to be listed, as before.
- The REST framework's browsable-API login (``/api-auth/login/``) and the Django admin login (``/admin/login/``)
  now send users to the TOM login page — administrators, too, pass through the two-factor challenge.
- Authentication events are written to the ``tom_common.security`` logger.

7.) Optional: enable the new controls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two-factor enforcement, password rules and expiry, terms of service, required profile fields and API-token controls
are each one setting away; see :doc:`Accounts and Authentication <../common/authentication>` and
:doc:`Custom settings <../common/customsettings>`.


.. _upgrade-v2-v3:

Upgrade from v2 to v3
---------------------

The upgrade from v2 to v3 involves several breaking changes that need to be handled by any TOM trying update to version 3.
Please follow the next steps in order to avoid complications.

1.) Update your `tomtoolkit` and `tom_app` dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This step depends on your dependency manager, but first you will need to update your TOM to depend on `tomtoolkit >=3.0.0`.
Most affiliated TOMToolkit apps will also need to be updated to their newest version.

If you use `poetry` or `uv` you will need to update your ``pyproject.toml``, otherwise check your ``requirements.txt``
or wherever else you keep your list of dependencies. 

Poetry
++++++

For example, using poetry, this should be as simple as bumping the version number to 

::

    "tomtoolkit>=3.0.0a11,<4"

in your ``pyproject.toml`` and running 

::

    poetry lock

to update the lock file. Aft this, you should be ready to install the updates with 

::

    poetry install

Requirements.txt
++++++++++++++++

If, instead, you have a ``requirements.txt`` file, edit the file and update you tomtoolkit dependency to

::

    tomtoolkit >= 3.0.0a11; < 4.0.0

Activate your virtual environment and install the updates using

::

    pip install -r requirements.txt


2.) Migrate your DB
~~~~~~~~~~~~~~~~~~~

.. Note::
    If you have already begun using the `default_settings` functionality described below, or you have previously updated to
    an alpha version of v3 (<3.0.0a11) then this migration may result in an error message. If you receive an error message
    stating that "app 'tom_alerts' isn't installed." Please add `tom_alerts` back into your installed apps before proceeding
    with this migration.

::

   ./manage.py migrate


3.) Migrate existing ReducedDatums
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This update changed how ReducedDatums are stored. We now have specific models for different types of data.
See the :ref:`Architecture Docs <ReducedDatum_label>` for a description, or 
:doc:`DataProducts API <../api/tom_dataproducts/models>` for a full code breakdown.

We want to update all of your existing data to this new scheme where possible. This could take some time for large databases.
Towards this end, we provide a `management command 
<https://github.com/TOMToolkit/tom_base/blob/dev/tom_dataproducts/management/commands/migrate_reduced_datums.py>`_
that will make "reasonable" assumptions about data values stored in ``ReducedDatum.value``. This command will search for
commonly used brightness fields, filter fields, spectroscopy data, etc. and translate them into the new ``ReducedDatum``
infrastructure. Anything unrecognized will remain in the catch-all ``value`` field. If you have highly customized fields
stored for your datums, you should consider copying and editing the management command to suit your needs.


.. Warning::
    This is a substantial DB change. Consider backing up your database before running this management command.

::

   ./manage.py migrate_reduced_datums

.. Note::
    Data validation during this migration is partially dependent on your database infrastructure. 
    You can test this migration by performing a dry run:

    ::

        ./manage.py migrate_reduced_datums --dry-run


.. _upgrade-v2-v3-settings:

4.) Update ``settings.py``
~~~~~~~~~~~~~~~~~~~~~~~~~~
Tomtoolkit now includes default settings stored in `tom_common.default_settings.py 
<https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/default_settings.py>`_ .
This prevents users from having to update their TOMs with mandatory settings allowing for more backward compatibility
with future changes. If you wish to use these settings, please make the following changes to your ``settings.py``:

.. code-block:: python
    :caption: settings.py
    :emphasize-lines: 4, 8, 13, 20

    import logging.config
    import os
    import tempfile
    from tom_common.default_settings import *

    ...

    # Replace your existing INSTALLED_APPS with the following:
    INSTALLED_APPS = TOMTOOLKIT_INSTALLED_APPS + [ 
        'custom_code',  # Include any apps you have installed for your TOM that are not in default_settings
    ]

    # Replace your existing MIDDLEWARE with the following:
    MIDDLEWARE = TOMTOOLKIT_MIDDLEWARE + [
        {{ custom_middleware }}  # Include any middleware you have installed for your TOM that are not in default_settings
    ]

    ...

    # Update the CRISPY_TEMPLATE_PACK:
    CRISPY_TEMPLATE_PACK = 'bootstrap5'

    ...

.. Note::

    This will incorporate all required settings changes, and will prevent future settings updates required by TOMToolkit.
    If you would rather not rely on the `default_settings`, here is the list of required changed:

    **Installed apps:**

    - Remove `tom_alerts` and `tom_catalogs`
    - Add `tom_dataservices`
    - Replace `bootstrap4` with `django_bootstrap5`
    - Replace `crispy_bootstrap4` with `crispy_bootstrap5`

    **Other Changes:**

    - Add `CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"`


5.) Update Custom Code
~~~~~~~~~~~~~~~~~~~~~~

Your custom code will likely need updates to be compatible with the v3 changes.
Pay special attention to the following areas:

Remove references to `tom_alerts` and `tom_catalogs`
++++++++++++++++++++++++++++++++++++++++++++++++++++

These apps were deprecated and will be removed from the toolkit within the next 6 months.
If you need to maintain these references until then, you just need to make sure they are included in your 
`INSTALLED_APPS` as they are not included in the `default_settings`.
Instead of these apps, use :doc:`tom_dataservices <../data_services/index>` for querying external sources.

Update references to `tom_dataproducts`
+++++++++++++++++++++++++++++++++++++++

Substantial updates were made to the `ReducedDatum` model infrastructure. The `ReducedDatum` model should not be used
in isolation anymore if possible. Instead, the sub models, `PhotometryReducedDatum`, `SpectroscopyReducedDatum`, and 
`AstrometryReducedDatum` should be used instead to improve communication between TOMs, and with the base TOMToolkit.

The `ReducedDatumCommon` can be extended to create new, specific data models if needed, and the existing `ReducedDatum`
model is still available for generic data, though all default references to it (such as processors) in the base toolkit
have been removed.

See the :ref:`Architecture Docs <ReducedDatum_label>` for a description of the current infrastructure, or 
:doc:`DataProducts API <../api/tom_dataproducts/models>` for a full code breakdown.

Upgrade to `bootstrap5`
+++++++++++++++++++++++

There are many invasive changes needed to upgrade to bootstrap5 from bootstrap4. These changes were necessary to stay
ahead of the curve as various projects and python distributions reach EOL.
Many of your templates may require changes.
We cannot go through a full list of the required changes here, but you can explore the following resources when attempting to implement your upgrade:

- `Bootsratp5 migration docs <https://getbootstrap.com/docs/5.0/migration/>`_
- `django-bootstrap5 migration docs <https://github.com/zostera/django-bootstrap5/blob/main/MIGRATE.md>`_
- `crispy-bootstrap5 updates <https://github.com/django-crispy-forms/crispy-bootstrap5>`_
- `TOMToolkit Bootstrap5 update PR <https://github.com/TOMToolkit/tom_base/pull/1571>`_


6.) Final Migration
~~~~~~~~~~~~~~~~~~~
New apps and custom_code changes will require a new migration. As always, take care when migrating and back up your Data base.

::

   ./manage.py migrate


Conclusion
~~~~~~~~~~
At this point, your TOM should be running on Version 3.  We know these were wide sweeping changes. If you have any
trouble with the upgrade, or find any bugs, please let us know by either making an issue on github, 
sending us a message on slack, or via email.
