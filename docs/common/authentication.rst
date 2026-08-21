Accounts and Authentication
===========================

.. Note::

    This page describes the accounts and authentication features introduced in TOM Toolkit 3.1. If you are
    upgrading an existing TOM, read :doc:`Updating your TOM <../introduction/updating>` first.

TOM Toolkit builds its user accounts on Django's ``django.contrib.auth`` and on
`django-allauth <https://docs.allauth.org/en/latest/>`_, the de-facto standard Django package for login,
registration, password management and multi-factor authentication. Out of the box your TOM behaves the way users
expect from any modern web application:

- users log in with a username and password and may enable **two-factor authentication** (an authenticator app
  plus recovery codes) from their profile page;
- administrators create accounts, or you can enable **self-registration** (open, or requiring administrator
  approval);
- users change their own password; with an email backend configured you can also offer **password reset by email**;
- every user has a personal **API token** for scripted access.

Everything stricter than that is **off by default** and switched on by settings: requiring two-factor
authentication, password composition rules and expiry, a terms-of-service agreement, mandatory profile fields,
and API-token expiry. Each control is general; how you combine them is up to your project's policy. Where a
setting comes from django-allauth we link to its documentation rather than repeat it.


Quick reference
---------------

All account pages live under ``/accounts/`` (served by django-allauth) except where noted. URL *names* are what
you use in templates (``{% url 'account_login' %}``) and code (``reverse('account_login')``). The historical names
``login`` and ``logout`` keep working as aliases.

.. list-table::
    :header-rows: 1
    :widths: 34 32 34

    * - Page
      - Path
      - URL name
    * - Log in
      - ``/accounts/login/``
      - ``account_login`` (alias ``login``)
    * - Log out (POST)
      - ``/accounts/logout/``
      - ``account_logout`` (alias ``logout``)
    * - Sign up (when registration is on)
      - ``/accounts/signup/``
      - ``account_signup``
    * - Account pending approval
      - ``/accounts/inactive/``
      - ``account_inactive``
    * - Change password
      - ``/accounts/password/change/``
      - ``account_change_password``
    * - Reset password (when enabled)
      - ``/accounts/password/reset/``
      - ``account_reset_password``
    * - Confirm it's you (re-authenticate)
      - ``/accounts/reauthenticate/``
      - ``account_reauthenticate``
    * - Two-factor overview
      - ``/accounts/2fa/``
      - ``mfa_index``
    * - Enable authenticator app
      - ``/accounts/2fa/totp/activate/``
      - ``mfa_activate_totp``
    * - Disable authenticator app
      - ``/accounts/2fa/totp/deactivate/``
      - ``mfa_deactivate_totp``
    * - Recovery codes
      - ``/accounts/2fa/recovery-codes/``
      - ``mfa_view_recovery_codes``
    * - Second-factor prompt at login
      - ``/accounts/2fa/authenticate/``
      - ``mfa_authenticate``
    * - Terms of service
      - ``/terms/``
      - ``terms-of-service``
    * - Accept terms of service
      - ``/terms/accept/``
      - ``terms-accept``
    * - Your profile
      - ``/users/profile/``
      - ``user-profile``
    * - Edit a user (and API token)
      - ``/users/<id>/update/``
      - ``user-update``
    * - Users and groups (pending users)
      - ``/users/``
      - ``user-list``


Logging in and out
------------------

The login page asks for a username and password. If the account has two-factor authentication enabled, a second
page asks for a code from the authenticator app (or a recovery code). Logging out is a ``POST`` (the navbar's
*Logout* button is a form), which is what Django 5 requires.

Repeated failed logins are rate-limited (by default: 5 failures per username in 5 minutes, and per-IP limits); the
user is told to wait. The limits are django-allauth's ``ACCOUNT_RATE_LIMITS`` (see
`Rate limits <https://docs.allauth.org/en/latest/account/rate_limits.html>`_) and are counted in Django's cache —
see :ref:`auth-deployment-notes` if your TOM runs more than one process.

Already-authenticated users who open the login page see the login form (not a redirect). TOM Toolkit relies on
this: when a logged-in user is denied access to a page, they are sent to the login page with a message explaining
that they need an account with more permissions.

The Django admin's own login page (``/admin/login/``) and the REST framework's browsable-API login both redirect
to the TOM login page, so there is no way to establish a browser session that skips two-factor authentication.


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

The sign-up form prompts for username, email, password, first and last name, organization/affiliation and
phone number; only fields listed in ``TOM_REQUIRED_USER_FIELDS`` are required, the others optional.
When a terms-of-service version is configured the form also requires the
*I accept the terms of service* checkbox (see :ref:`auth-terms`).

A *Register* button appears in the navbar and a link on the login page whenever registration is open.

.. Note::

    In TOM Toolkit 3.1, ``TOM_REGISTRATION_STRATEGY`` replaces the ``tom_registration`` plugin, which is
    deprecated. See :doc:`Updating your TOM <../introduction/updating>` for the mapping from ``tom_registration``'s
    settings, URL names and templates to their replacements.

Customizing registration
~~~~~~~~~~~~~~~~~~~~~~~~

Every piece of registration behaviour follows the same pattern: tom_base ships a default implementation (a form,
an adapter method, a template), and a setting names the implementation to use. To change a behaviour, subclass
the default in your TOM's ``custom_code`` app (or drop a template into your TOM's ``templates/`` directory) and
point the setting at your version in ``settings.py`` — nothing in tom_base changes.

- **Extra sign-up fields**: subclass ``tom_common.forms.TomSignupForm`` in your ``custom_code`` app, add fields, and
  store them in ``signup(self, request, user)``; point django-allauth at it with
  ``ACCOUNT_SIGNUP_FORM_CLASS = 'custom_code.forms.MySignupForm'``.
- **Behaviour** (who may sign up, which group new users join, notification emails, redirects): subclass
  ``tom_common.adapters.TomAccountAdapter`` and set ``ACCOUNT_ADAPTER = 'custom_code.adapters.MyAccountAdapter'``.
  See `Adapter <https://docs.allauth.org/en/latest/account/adapter.html>`_ for the available hooks.
- **Templates**: ``account/signup.html``, ``account/signup_closed.html``, ``account/account_inactive.html`` and the
  email templates above can be overridden in your TOM's ``templates/`` directory.


Two-factor authentication
-------------------------

Two-factor authentication (2FA, also called multi-factor authentication or MFA) uses a **time-based one-time
password** (TOTP) from an authenticator app — Microsoft Authenticator, Google Authenticator, Authy, 1Password,
Bitwarden and similar all work — plus a set of **recovery codes** for when the app is unavailable.

For users
~~~~~~~~~

1. Open your profile (your name in the navbar → *Profile*) and click *Enable two-factor authentication* on the
   *Security* card (or go to ``/accounts/2fa/``).
2. Scan the QR code with your authenticator app (or type the key shown below it), then enter the 6-digit code the
   app displays.
3. Save the recovery codes that are shown **once**. Each code can be used one time in place of an app code.

From then on, login asks for a code after the password. The *Security* card shows whether 2FA is enabled and links
to the two-factor management page, where you can regenerate recovery codes (codes are displayed only when they are
generated) or disable the app. Sensitive actions (changing 2FA settings, regenerating an
API token when required) ask you to confirm your password or a code again if your last login was more than a few
minutes ago.

If you lose both the app and the recovery codes, an administrator can remove your authenticator in the Django admin
(*Multi-factor authentication* → *Authenticators*); you then enrol again.

For TOM developers
~~~~~~~~~~~~~~~~~~

2FA is always available to every user and is by default optional. To require it, set::

    TOM_MFA_REQUIRED = 'all'         # or 'superusers' to require it only for superusers

After login, users who have not enrolled are taken to the enrolment page and cannot use the rest of the TOM until
they have. ``'all'`` applies to every user including superusers (and to social/SSO logins if you add them); the
default, ``None``, enforces nothing.
While ``TOM_MFA_REQUIRED`` is set, users cannot disable their authenticator app (an administrator can still remove it).

The issuer shown in authenticator apps is your ``TOM_NAME``. TOTP secrets and recovery codes are stored encrypted
with the key derived from ``SECRET_KEY`` (see :doc:`Encryption and the SECRET_KEY <../deployment/encryption>`; the
``rotate_encryption_key`` command re-encrypts them when you rotate the key).

Other django-allauth MFA settings (``MFA_SUPPORTED_TYPES``, ``MFA_TOTP_TOLERANCE``, ``MFA_RECOVERY_CODE_COUNT`` …)
can be set in ``settings.py``; see `MFA configuration <https://docs.allauth.org/en/latest/mfa/configuration.html>`_.
TOM Toolkit enables TOTP and recovery codes; passkeys/WebAuthn are not enabled.


Passwords
---------

Users can change their password on their profile edit page (``/users/<id>/update/``) or at
``/accounts/password/change/``. Superusers can set another user's password from the *Users* page; a password set
this way must be changed by the user at their next login when password expiry is enabled.

Password rules
~~~~~~~~~~~~~~

Password rules are Django's ``AUTH_PASSWORD_VALIDATORS`` and apply everywhere a password is set (sign-up, change,
reset, admin). TOM Toolkit adds two validators you can include:

``tom_common.password_validation.CharacterClassValidator``
    Requires at least one upper-case letter, one lower-case letter, one digit and one special character.

``tom_common.password_validation.NotSameAsCurrentPasswordValidator``
    Rejects a "new" password identical to the current one (useful together with expiry).

For example, a policy of 12+ characters with all four character classes, different from the user's name and email::

    AUTH_PASSWORD_VALIDATORS = [
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'tom_common.password_validation.CharacterClassValidator'},
        {'NAME': 'tom_common.password_validation.NotSameAsCurrentPasswordValidator'},
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
accept them. Acceptances are recorded with the version, time and IP address. To update your terms, **change the version string** (any
string — a date or a number) and everyone will be prompted to accept the updated terms.

Write your terms in the template ``tom_common/partials/terms_of_service_text.html`` in your TOM's ``templates/``
directory (plain HTML). They are shown at ``/terms/`` and on the acceptance page.


.. _auth-profile-fields:

Profile fields
--------------

In addition to Django's first name, last name and email, TOM Toolkit adds *organization / affiliation* and *phone number*
fields to a user's profile. To make any of these mandatory, add them to ``TOM_REQUIRED_USER_FIELDS``::

    TOM_REQUIRED_USER_FIELDS = ['first_name', 'last_name', 'email', 'affiliation', 'phone_number']    # default []

Required fields are enforced on the sign-up form and the user edit form, and a logged-in user whose profile is
missing a required field is redirected to their profile edit page until it is complete.

Projects that need more profile fields add their own model in ``custom_code`` and show it on the profile page with
the ``profile_details()`` integration point (see :doc:`Customizing templates <../customization/customize_templates>`).


API access
----------

Every user has a personal API token, shown on their profile and regenerable from their profile edit page; see
:doc:`Accessing data through the REST API <../managing_data/accessing_data_through_REST_API>`. Two settings tighten
API access::

    TOM_API_TOKEN_EXPIRY_DAYS = 60        # default None: tokens do not expire
    TOM_API_TOKEN_REQUIRES_MFA = True     # default False

- With an expiry, requests with a token older than the limit are rejected (HTTP 401 with an explanatory message);
  the user regenerates the token on their edit page, which shows when it was created and when it expires.
- With ``TOM_API_TOKEN_REQUIRES_MFA``: the password-only ``/api/token-auth/`` endpoint is disabled; a token is only
  accepted if its user has two-factor authentication enabled and the token was created after enrolment; tokens
  can only be (re)generated by the user themself, after re-authenticating; and the token is rejected while the
  account has an outstanding requirement (expired password, terms not accepted).

Both are enforced by ``tom_common.api_auth.TomTokenAuthentication``, which replaces the plain REST framework
``TokenAuthentication`` in ``REST_FRAMEWORK``::

    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'tom_common.api_auth.TomTokenAuthentication',            # Authorization: Token <key>
            'rest_framework.authentication.SessionAuthentication',   # logged-in browsers
            # 'rest_framework.authentication.BasicAuthentication',   # username/password per request — omit when
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
reset pages are open automatically — you do not need to add them to ``OPEN_URLS``. As before, ``/api/`` paths that
scripts reach with a token must be listed in ``OPEN_URLS``.


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
    ``ACCOUNT_ADAPTER`` (default ``tom_common.adapters.TomAccountAdapter``) controls registration, redirects,
    email sending and the inactive-account response; ``MFA_ADAPTER`` (default ``tom_common.adapters.TomMFAAdapter``)
    controls the issuer name, secret encryption and whether users may remove their authenticator. Subclass the
    TOM Toolkit adapter and override the hook you need.
Password validators
    ``AUTH_PASSWORD_VALIDATORS`` (above).
Post-login requirements
    ``TOM_ACCOUNT_REQUIREMENTS`` is the ordered list of checks run for every logged-in request::

        TOM_ACCOUNT_REQUIREMENTS = [
            'tom_common.account_requirements.terms_of_service_accepted',
            'tom_common.account_requirements.mfa_enrolled',
            'tom_common.account_requirements.password_not_expired',
            'tom_common.account_requirements.required_fields_present',
        ]

    Each built-in check is a function whose companion ``TOM_*`` setting is its parameter: unconfigured means the
    check does nothing. Add your own: a function taking the request and returning ``None`` (requirement met) or
    the URL name of the page that lets the user meet it; give it its own ``settings.py`` value if it needs one,
    following the same inactive-unless-configured pattern. The pages you return are exempt from the check
    automatically, as are logout, the account pages and static files. Requests
    from scripts using a token are not subject to these checks (see API access above).
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
  with your ``TOM_NAME``.
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
