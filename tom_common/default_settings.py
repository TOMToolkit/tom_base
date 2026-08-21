"""
Default settings for TOM Toolkits.

This sets all of the mandatory apps and middleware as defaults

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

TOMTOOLKIT_INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_extensions',
    'django_tasks',
    'django_tasks.backends.database',
    'guardian',
    'tom_common',
    'allauth',  # after tom_common so our template overrides take precedence over allauth's.
    'allauth.account',
    'allauth.mfa',
    'django_comments',
    'django_bootstrap5',
    'crispy_bootstrap5',
    'crispy_forms',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'django_tables2',
    'django_gravatar',
    'django_htmx',
    'tom_targets',
    'tom_observations',
    'tom_dataproducts',
    'tom_dataservices',
    'tom_calendar',
]

TOMTOOLKIT_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # required by allauth; must follow AuthenticationMiddleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'tom_common.middleware.Raise403Middleware',
    'tom_common.middleware.ExternalServiceMiddleware',
    'tom_common.middleware.AuthStrategyMiddleware',
]

TOMTOOLKIT_AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',  # show "pending approval" for inactive accounts
    'guardian.backends.ObjectPermissionBackend',
)
AUTHENTICATION_BACKENDS = TOMTOOLKIT_AUTHENTICATION_BACKENDS

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# django-allauth configuration.
ACCOUNT_ADAPTER = 'tom_common.adapters.TomAccountAdapter'
MFA_ADAPTER = 'tom_common.adapters.TomMFAAdapter'
ACCOUNT_LOGIN_METHODS = {'username'}
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = False  # prevent redirect loops; redirect to login with message
MFA_SUPPORTED_TYPES = ['totp', 'recovery_codes']  # passkeys/WebAuthn deliberately not enabled
MFA_ALLOW_UNVERIFIED_EMAIL = True
MFA_TOTP_TOLERANCE = 1  # accept codes from the adjacent 30 s window (clock skew)
MFA_RECOVERY_CODES_SHOW_ONCE = True  # recovery codes are displayed only at generation time

# TOM Toolkit account settings (each documented in docs/common/customsettings.rst)
TOM_PASSWORD_RESET_ENABLED = False  # password reset by email; requires a working EMAIL_BACKEND

# Backwards typo compatibility
TOMTOOKIT_INSTALLED_APPS = TOMTOOLKIT_INSTALLED_APPS
TOMTOOKIT_MIDDLEWARE = TOMTOOLKIT_MIDDLEWARE
