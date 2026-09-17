Accounts and Authentication
===========================

.. Note::

    This page describes the accounts and authentication features introduced in TOM Toolkit 3.1. If you are
    upgrading an existing TOM, see :doc:`Updating your TOM <../introduction/updating>`.

TOM Toolkit builds its user accounts on Django's ``django.contrib.auth`` and on
`django-allauth <https://docs.allauth.org/en/latest/>`_, the de-facto standard Django package for login,
registration, password management and multi-factor authentication. Out of the box, your TOM behaves the way
users expect from any modern web application:

- users log in with a username and password and may enable **two-factor authentication** (an authenticator app
  plus recovery codes) from their profile page;
- administrators create accounts, or you can enable **self-registration** (open, or requiring administrator
  approval);
- users change their own password; when an email backend is configured, you can also offer
  **password reset by email**;
- every user has a personal **API token** for scripted access.

Anything more strict than those defaults is switched on by configuration settings: requiring two-factor
authentication, password composition rules and expiry, a terms-of-service agreement, mandatory profile fields,
and API-token expiry. Each control is general; how you combine them is up to your project's policy. Example
combinations are collected in :doc:`Common accounts scenarios <authentication_scenarios>`.


Creating accounts and self-registration
---------------------------------------

By default only superusers create accounts (*Users* → *Add user*). To let people register
themselves, set ``TOM_REGISTRATION_STRATEGY`` in ``settings.py``:

``None`` (default)
    No self-registration. ``/accounts/signup/`` shows a "registration is closed" page inviting the visitor to
    contact the TOM's administrators for an account.

``'open'``
    Visitors fill in the sign-up form and are logged in immediately. New users are added to the ``Public`` group.

``'approval_required'``
    Visitors fill in the sign-up form; the account is created **inactive** and added to the ``Public`` group. A
    superuser approves it from the *Pending users* table on the *Users* page (``/users/``). Until then the user sees
    an "account pending approval" page when they try to log in. If an email backend is configured, the addresses in
    ``settings.MANAGERS`` are notified of each request and the user is notified when approved (templates
    ``account/email/registration_requested_*.txt`` and ``account/email/registration_approved_*.txt``; sender
    ``DEFAULT_FROM_EMAIL``).

    A working email backend is effectively a prerequisite for a smooth ``'approval_required'`` flow. Without one
    the flow still works, but nobody is notified of anything: the *Pending users* table makes this explicit and
    the approver is instructed to inform the user directly. Additionally, ``manage.py check`` warns
    of this (no email) situation (``tom_common.W002``).

The sign-up form prompts for username, email, password, first and last name, organization/affiliation and
phone number; only fields listed in ``TOM_REQUIRED_USER_FIELDS`` are required, any others are optional.
When a terms-of-service version is configured the form also requires the
*I accept the terms of service* checkbox (see :ref:`auth-terms`).

A *Register* button appears in the navbar and a link on the login page whenever registration is open.

.. Note::

    In TOM Toolkit 3.1, ``TOM_REGISTRATION_STRATEGY`` replaces the ``tom_registration`` plugin, which is
    deprecated. See :doc:`Updating your TOM <../introduction/updating>` for the mapping from ``tom_registration``'s
    settings, URL names and templates to their replacements.

Customizing registration
~~~~~~~~~~~~~~~~~~~~~~~~

Every piece of registration behavior follows the same pattern: tom_base ships a default implementation (a form,
an adapter method, a template), and a setting names the implementation to use. To change a behavior, subclass
the default in your TOM's ``custom_code`` app (or drop a template into your TOM's ``templates/`` directory) and
point the setting at your version in ``settings.py``.

- **Extra sign-up fields**: subclass ``tom_common.accounts.forms.TomSignupForm`` in your ``custom_code`` app,
  add fields, and store them in ``signup(self, request, user)``; point django-allauth at it with
  ``ACCOUNT_SIGNUP_FORM_CLASS = 'custom_code.forms.MySignupForm'``.
- **Sign-up Behavior** (who may sign up, which group new users join, notification emails, redirects): subclass
  ``tom_common.accounts.adapters.TomAccountAdapter`` and set, for example,
  ``ACCOUNT_ADAPTER = 'custom_code.adapters.MyAccountAdapter'``.
  See `Adapter <https://docs.allauth.org/en/latest/account/adapter.html>`_ for the available hooks.
- **Templates**: ``account/signup.html``, ``account/signup_closed.html``, ``account/account_inactive.html`` and the
  email templates above can be overridden in your TOM's ``templates/`` directory. (This is the ``templates/``
  directory at the top level of your TOM, sibling to your ``manage.py`` module).


Two-factor authentication
-------------------------

Two-factor authentication (2FA, also called multi-factor authentication or MFA) uses a **time-based one-time
password** (TOTP) from an authenticator app. Microsoft Authenticator, Google Authenticator, Authy, 1Password,
Bitwarden and similar all work. A set of **recovery codes** is supplied for when an authenticator app is unavailable.

2FA From the User's Perspective
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open your profile (click on your name in the navbar → *Profile*) and click *Enable two-factor authentication*
   on the *Security* card (or go to ``/accounts/2fa/``).
2. Scan the QR code with your authenticator app (or type the key shown below it), then enter the 6-digit code the
   authenticator app displays.
3. Save the recovery codes. Each code can be used one time in place of an app code. By default, a new set of
   recovery codes is available from the *Security* card of your profile page.

From then on, login asks for a code after the password. The *Security* card shows whether 2FA is enabled and links
to the two-factor management page, where you can view, download, or regenerate your recovery codes, or disable the
app. Sensitive actions (changing 2FA settings, regenerating an API token when required) ask you to confirm your
password or a code again if your last login was more than a few minutes ago.

If you lose both the app and the recovery codes, an administrator can reset your authenticator in the Django admin
page (*Multi-factor authentication* → *Authenticators*) and you then can enroll again.

From the TOM developer's Perspective
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

2FA is always available to every user and is optional by default. To require it, set::

    TOM_MFA_REQUIRED = 'all'  # or 'superusers' to require it only for privileged users

After login, users who have not yet enabled 2FA are taken to the enrollment page and cannot use the rest of
the TOM until 2FA enabled. When ``TOM_MFA_REQUIRED = 'all'``, ``'all'`` means every user including superusers
(and to social/SSO logins if you configure them); the default, ``None``, means 2FA is optional.
When ``TOM_MFA_REQUIRED`` is set, users cannot disable their authenticator app (but an administrator can still
reset it).

Other django-allauth MFA settings (``MFA_SUPPORTED_TYPES``, ``MFA_TOTP_TOLERANCE``, ``MFA_RECOVERY_CODE_COUNT`` …)
can be set in ``settings.py``; see `MFA configuration <https://docs.allauth.org/en/latest/mfa/configuration.html>`_.
TOM Toolkit enables TOTP and recovery codes; passkeys/WebAuthn are not enabled (contact us if you need this).


Passwords
---------

Users can change their password on their profile edit page (``/users/<id>/update/``) or at
``/accounts/password/change/``. Superusers can set another user's password from the *Users* page; a password set
this way must be changed by the user at their next login when password expiry is enabled.

Password constraints
~~~~~~~~~~~~~~~~~~~~

By default, password constraits are Django's ``AUTH_PASSWORD_VALIDATORS``.
TOM Toolkit adds two validators you can include:

``tom_common.accounts.password_validation.CharacterClassValidator``
    Requires at least one upper-case letter, one lower-case letter, one digit and one special character.

``tom_common.accounts.password_validation.NotSameAsCurrentPasswordValidator``
    Rejects a "new" password identical to the current one (useful together with expiry).

For example, a policy of 12+ characters with all four character classes, different from the user's name and email::

    AUTH_PASSWORD_VALIDATORS = [
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
         'OPTIONS': {'min_length': 12}
        },
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'tom_common.accounts.password_validation.CharacterClassValidator'},
        {'NAME': 'tom_common.accounts.password_validation.NotSameAsCurrentPasswordValidator'},
    ]

You can write your own validator class in ``custom_code`` and list it the same way (see
`Django password validation <https://docs.djangoproject.com/en/stable/topics/auth/passwords/#password-validation>`_).

.. Note::

    Current guidance (NIST SP 800-63B) favours long passphrases and multi-factor authentication over password composition
    rules and periodic expiry. TOM Toolkit provides the capabilities to implement your specific hosting policy requirements.

Password expiry
~~~~~~~~~~~~~~~

::

    TOM_PASSWORD_EXPIRY_DAYS = 60    # default None (never expires)

When set, a user whose password is older than this is redirected to the change-password page after login (and on
any later request) until they change it. The age is counted from the last change; a password set by an
administrator counts as expired. When you first enable expiry, passwords last changed before the upgrade are
treated as old, so most existing users are asked to change their password once.

Password reset by email
~~~~~~~~~~~~~~~~~~~~~~~

::

    TOM_PASSWORD_RESET_ENABLED = True    # default False

Adds a *Forgot your password?* link to the login page and enables django-allauth's reset-by-email flow. This
requires a working email configuration (``EMAIL_BACKEND``, ``DEFAULT_FROM_EMAIL`` …). When it is off the reset pages
are not served at all, so a TOM without email cannot leak "unknown account" mails or error on them.


.. _auth-terms:

Terms of service
----------------

::

    TOM_TERMS_OF_SERVICE_VERSION = '2026-09-01'    # default None (no terms)

When set, every user must accept the current terms before using the TOM: new users tick a checkbox on the sign-up
form; existing users (and users created by an administrator) are shown the terms right after logging in and must
accept them. Acceptances are recorded with the version, time and IP address. To update your terms,
**change the version string** and users will be prompted to accept the updated terms.

Write your terms in the template ``tom_common/partials/terms_of_service_text.html`` in your TOM's ``templates/``
directory (plain HTML). They are shown at the ``/terms/`` page and on the acceptance page.


.. _auth-profile-fields:

Profile fields
--------------

In addition to Django's first name, last name and email, TOM Toolkit adds *organization / affiliation* and *phone number*
fields to a user's profile. To make any of these mandatory, add them to ``TOM_REQUIRED_USER_FIELDS``::

    TOM_REQUIRED_USER_FIELDS = ['first_name', 'last_name', 'email']    # default []

Required fields are enforced on the sign-up form and the user edit form, and a logged-in user whose profile is
missing a required field is redirected to their profile edit page until it is complete.

Projects that need more profile fields add their own model in ``custom_code`` and show it on the profile page with
the ``profile_details()`` integration point (see :doc:`Customizing templates <../customization/customize_templates>`).


API access
----------

Every user has a personal API token, shown on their profile and regenerable from their profile edit page; see
:doc:`Accessing data through the REST API <../managing_data/accessing_data_through_REST_API>`. Two settings
can customize API access::

    TOM_API_TOKEN_EXPIRY_DAYS = 60        # default None: tokens do not expire
    TOM_API_TOKEN_REQUIRES_MFA = True     # default False

- With an expiry, requests with a token older than the limit are rejected (HTTP 401 with an explanatory message);
  the user regenerates the token on their edit page, which shows when it was created and when it expires.
- With ``TOM_API_TOKEN_REQUIRES_MFA``: the password-only ``/api/token-auth/`` endpoint is disabled (because this
  would by-pass the second factor).

Both are enforced by ``tom_common.accounts.api_auth.TomTokenAuthentication``, which replaces the plain REST framework
``TokenAuthentication`` in ``REST_FRAMEWORK``::

    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'tom_common.accounts.api_auth.TomTokenAuthentication',   # Authorization: Token <key>
            'rest_framework.authentication.SessionAuthentication',   # logged-in browsers
            # 'rest_framework.authentication.BasicAuthentication',   # username/password per request; omit this when
                                                                     # you require two-factor authentication
        ],
        ...
    }

Browser sessions (``SessionAuthentication``) are protected by the normal login, including 2FA.

.. Note::

    TOM-to-TOM data sharing (``DATA_SHARING``) currently authenticates with the destination's username and
    password (HTTP Basic). A destination that turns off ``BasicAuthentication`` must give its partners tokens
    instead; support for ``API_TOKEN`` in ``DATA_SHARING`` is planned.


Access strategy and open URLs
-----------------------------

With ``AUTH_STRATEGY = 'LOCKED'`` the login, sign-up, second-factor, pending-approval and (when enabled) password
reset pages are open automatically. They are to ``OPEN_URLS`` to enable the authorization process. As before,
``/api/`` paths that scripts reach with a token must be listed in ``OPEN_URLS``.


Customizing the authentication pages and behaviour
--------------------------------------------------

Everything below is done in your TOM (``settings.py``, ``templates/``, ``custom_code``); nothing in tom_base
needs to change.

Templates
    The account pages are django-allauth templates rendered inside your TOM's ``tom_common/base.html``. To restyle
    all of them at once, override ``allauth/layouts/base.html`` and the small element templates under
    ``allauth/elements/`` (TOM Toolkit ships Bootstrap 5 versions of ``fields``, ``field``, ``button``,
    ``button_group`` and ``panel``). To change one page, override its template (``account/login.html``,
    ``account/signup.html``, ``mfa/index.html`` …). Template names are listed in the
    `django-allauth template documentation <https://docs.allauth.org/en/latest/common/templates.html>`_.
Forms
    ``ACCOUNT_FORMS = {'login': 'custom_code.forms.MyLoginForm'}`` (and ``signup``, ``change_password`` …)
    replace individual forms; ``MFA_FORMS`` does the same for the 2FA forms. See
    `Forms <https://docs.allauth.org/en/latest/account/forms.html>`_.
Adapters
    ``ACCOUNT_ADAPTER`` (default ``tom_common.accounts.adapters.TomAccountAdapter``) controls registration, redirects,
    email sending and the inactive-account response; ``MFA_ADAPTER`` (default ``tom_common.accounts.adapters.TomMFAAdapter``)
    controls the issuer name, secret encryption and whether users may remove their authenticator. Subclass the
    TOM Toolkit adapter and override the hook you need.
Password validators
    ``AUTH_PASSWORD_VALIDATORS`` (see above).
Post-login requirements
    ``TOM_ACCOUNT_REQUIREMENTS`` is the ordered list of checks run for every logged-in request::

        TOM_ACCOUNT_REQUIREMENTS = [
            'tom_common.accounts.requirements.terms_of_service_accepted',
            'tom_common.accounts.requirements.mfa_enrolled',
            'tom_common.accounts.requirements.password_not_expired',
            'tom_common.accounts.requirements.required_fields_present',
        ]

    Each built-in check is a function whose companion ``TOM_*`` setting is its parameter: unconfigured means the
    check does nothing. Every *configured* requirement also appears as a column on the *Users* page, so
    administrators can see it's status at a glace.
    
    To add your own: Define a function taking the request and
    returning ``None`` (meaning the requirement is met) or, if the requirement is not met, the URL name of the
    page that the user should be directed to in order to meet the requirement.
    Alternatively, to also get a *Users*-page column, create a subclass
    ``tom_common.accounts.requirements.AccountRequirement``. Define ``label``, ``is_configured()`` and
    ``is_met(user)``. To pass configuration values, define it its own ``settings.py`` value
    following the same inactive-unless-configured pattern. The pages you return are exempt from the
    check automatically (presumably, they need to be accessed to meet the requirement), as are logout,
    the account pages and static files. Requests from scripts using a token are not subject to these checks
    (see API access above).
Social / single sign-on
    django-allauth's ``socialaccount`` app (ORCID, GitHub, Google, OpenID Connect providers …) can be added to a
    TOM alongside the TOM Toolkit integration; social logins go through the same second-factor and post-login
    checks. TOM Toolkit does not configure any provider for you; see
    `Social account <https://docs.allauth.org/en/latest/socialaccount/index.html>`_.


.. _auth-deployment-notes:

Deployment notes
----------------

- **Cache**: login rate limits and one-time-code replay protection are stored in Django's ``CACHES``. The default
  file cache in a temporary directory is per machine; if your TOM runs several processes on different hosts (or
  containers), use a shared cache (database cache, Redis, Memcached).
- **Reverse proxies**: django-allauth does not trust ``X-Forwarded-For`` unless you set
  ``ALLAUTH_TRUSTED_PROXY_COUNT`` to the number of proxies in front of your TOM; otherwise all users share the
  proxy's IP for rate limiting and in terms-of-service records.
- **Sessions**: consider ``SESSION_COOKIE_AGE``, ``SESSION_SAVE_EVERY_REQUEST`` (idle timeout),
  ``SESSION_EXPIRE_AT_BROWSER_CLOSE``, ``SESSION_COOKIE_SECURE``/``CSRF_COOKIE_SECURE`` and
  ``ACCOUNT_SESSION_REMEMBER = False`` (hide "Remember me") for stricter environments. See
  :doc:`Deployment tips <../deployment/deployment_tips>`.
- **Email**: self-registration notifications, password reset and any django-allauth email feature need a working
  ``EMAIL_BACKEND``; sender addresses come from ``DEFAULT_FROM_EMAIL`` and ``SERVER_EMAIL``; subjects are prefixed
  with your ``TOM_NAME``. ``manage.py check`` warns (``tom_common.W002``) when approval-required registration or
  password reset is enabled without an email backend; if email cannot be sent, the user or the approver
  is instead informed of this in the UI.
- **Security log**: login success/failure, logout, password changes, two-factor enrolment/removal, API-token
  regeneration and terms acceptance are logged to the ``tom_common.security`` logger at ``INFO``. Route it to a
  file or your log collector in ``LOGGING``.
- **Site**: django-allauth uses ``django.contrib.sites``; keep ``SITE_ID`` in your settings (it is there by default).


Settings reference
------------------

All settings introduced on this page are documented in :doc:`Custom settings <customsettings>`:
``TOM_REGISTRATION_STRATEGY``, ``TOM_MFA_REQUIRED``, ``TOM_PASSWORD_EXPIRY_DAYS``, ``TOM_PASSWORD_RESET_ENABLED``,
``TOM_TERMS_OF_SERVICE_VERSION``, ``TOM_REQUIRED_USER_FIELDS``, ``TOM_API_TOKEN_EXPIRY_DAYS``,
``TOM_API_TOKEN_REQUIRES_MFA``, ``TOM_ACCOUNT_REQUIREMENTS``. django-allauth's own settings (``ACCOUNT_*``,
``MFA_*``) are documented at `docs.allauth.org <https://docs.allauth.org/en/latest/>`_.
