Common Accounts Scenarios
=========================

Three worked configurations combining the controls from :doc:`Accounts and Authentication
<authentication>`. Each shows the complete ``settings.py`` recipe and what your users
experience. Settings not shown keep their defaults; settings are documented in
:doc:`Custom settings <customsettings>`.

A public TOM with optional two-factor authentication
----------------------------------------------------

This is the out-of-the-box configuration. For a TOM whose pages are public
(the default ``READ_ONLY`` strategy) and whose collaborators get accounts from an
administrator:

.. code-block:: python

    # settings.py: no changes. (This is the default behavior).

What you get: anonymous visitors browse but cannot change anything; administrators create
accounts from the *Users* page; every user *may* enable two-factor authentication from the
*Security* card on their profile page. The *Users* page shows who has MFA enabled. To require
MFA on privileged accounts while leaving it optional otherwise::

    TOM_MFA_REQUIRED = 'superusers'  # MFA required for privileged users; optional otherwise.

A locked TOM with self-registration
-----------------------------------

For a TOM serving a collaboration whose data is private, but whose number of users is large
enough that administrators should not create every account by hand. Users register themselves
and an administrator approves each one.

.. code-block:: python

    AUTH_STRATEGY = 'LOCKED'
    TOM_REGISTRATION_STRATEGY = 'approval_required'
    TOM_PASSWORD_RESET_ENABLED = True
    TOM_REQUIRED_USER_FIELDS = ['first_name', 'last_name', 'email', 'affiliation']

    # the notifications this flow sends need working email:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['EMAIL_HOST']          # and EMAIL_PORT, EMAIL_USE_TLS, credentials
    DEFAULT_FROM_EMAIL = SERVER_EMAIL = os.environ['DEFAULT_FROM_EMAIL']
    MANAGERS = [('TOM administrators', os.environ['TOM_ADMIN_EMAIL'])]

What you get: every TOM page requires login (except for pages required for registration).
A *Register* button is placed in the navbar; applicants fill
in the required fields, wait on the "pending approval" page, and ``MANAGERS`` are emailed;
an administrator approves the registration request from the *Pending users* table and the
new user is emailed a login link. Without working email, the flow still works, but you
must tell applicants yourself. ``manage.py check`` warns of this (no email) situation.

A strict hosting policy
-----------------------

For a TOM with mandatory two-factor authentication, password composition and expiry rules,
terms-of-service acceptance, and API-token controls. 

.. code-block:: python

    TOM_MFA_REQUIRED = 'all'
    TOM_PASSWORD_EXPIRY_DAYS = 60
    TOM_TERMS_OF_SERVICE_VERSION = '2026-09-01'    # bump the string to require re-acceptance
    TOM_REQUIRED_USER_FIELDS = ['first_name', 'last_name', 'email', 'affiliation', 'phone_number']
    TOM_API_TOKEN_EXPIRY_DAYS = 60
    TOM_API_TOKEN_REQUIRES_MFA = True

    AUTH_PASSWORD_VALIDATORS = [
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'tom_common.accounts.password_validation.CharacterClassValidator'},
        {'NAME': 'tom_common.accounts.password_validation.NotSameAsCurrentPasswordValidator'},
    ]

    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'tom_common.accounts.api_auth.TomTokenAuthentication',  # API token requires MFA enabled
            'rest_framework.authentication.SessionAuthentication',
            # no BasicAuthentication: per-request passwords would bypass the second factor
        ],
        'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    }

Write your terms of service in ``templates/tom_common/partials/terms_of_service_text.html``.
(This is the ``templates`` directory at the top level of your TOM, sibling to your
``manage.py`` module).

What you get: after logging in, every user is walked through accepting the terms,
enrolling an authenticator app, replacing an expired (or administrator-set) password, and
completing missing profile fields.