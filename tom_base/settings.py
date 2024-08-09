"""
Django settings for tom_base project.

Generated by 'django-admin startproject' using Django 2.0.6.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""
import logging.config
import os
import tempfile


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'testkey')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['']

# Application definition

TOM_NAME = 'TOM Toolkit'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_extensions',
    'guardian',
    'tom_common',
    'django_comments',
    'bootstrap4',
    'crispy_bootstrap4',
    'crispy_forms',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'django_gravatar',
    'tom_targets',
    'tom_alerts',
    'tom_catalogs',
    'tom_observations',
    'tom_dataproducts',
    'tom_dataservices',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tom_common.middleware.Raise403Middleware',
    'tom_common.middleware.ExternalServiceMiddleware',
    'tom_common.middleware.AuthStrategyMiddleware',
]

ROOT_URLCONF = 'tom_common.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

CRISPY_TEMPLATE_PACK = 'bootstrap4'

WSGI_APPLICATION = 'tom_base.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = False

USE_TZ = True

DATETIME_FORMAT = 'Y-m-d H:i:s'
DATE_FORMAT = 'Y-m-d'


# Caching
# https://docs.djangoproject.com/en/dev/topics/cache/#filesystem-caching

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': tempfile.gettempdir()
    }
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'data')
MEDIA_URL = '/data/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO'
        }
    }
}
logging.config.dictConfig(LOGGING)

TARGET_TYPE = 'SIDEREAL'
FACILITIES = {
    'LCO': {
        'portal_url': 'https://observe.lco.global',
        'api_key': os.getenv('LCO_API_KEY', ''),
    },
}


TOM_FACILITY_CLASSES = [
    'tom_observations.facilities.lco.LCOFacility',
    'tom_observations.facilities.gemini.GEMFacility',
    'tom_observations.facilities.soar.SOARFacility',
    'tom_observations.facilities.lt.LTFacility',

]

# Define MATCH_MANAGERS here.
# This is a dictionary with the key set to a given model class name and the value as a dotted module path to the desired
# match manager for the named model.
# See https://tom-toolkit.readthedocs.io/en/latest/targets/target_matcher.html
# For example:
# MATCH_MANAGERS = {
#    'Target': 'custom_code_directory.match_managers.MyCustomTargetMatchManager'
# }
MATCH_MANAGERS = {}

#
# tom_alerts configuration
#

#
# tom_dataproducts configuration
#
# Define the valid data product types for your TOM.
# This is a dictionary of tuples to be used as ChoiceField options, with the first element being the type and the
# second being the display name.
# Be careful when removing items, as previously valid types will no
# longer be valid, and may cause issues unless the offending records are modified.
DATA_PRODUCT_TYPES = {
    'photometry': ('photometry', 'Photometry'),
    'fits_file': ('fits_file', 'FITS File'),
    'spectroscopy': ('spectroscopy', 'Spectroscopy'),
    'image_file': ('image_file', 'Image File')
}

DATA_PROCESSORS = {
    'photometry': 'tom_dataproducts.processors.photometry_processor.PhotometryProcessor',
    'spectroscopy': 'tom_dataproducts.processors.spectroscopy_processor.SpectroscopyProcessor',
}

# Configuration for the TOM/Kafka Stream receiving data from this TOM
# DATA_SHARING = {
#     'hermes': {
#         'DISPLAY_NAME': os.getenv('HERMES_DISPLAY_NAME', 'Hermes'),
#         'BASE_URL': os.getenv('HERMES_BASE_URL', 'https://hermes.lco.global/'),
#         'CREDENTIAL_USERNAME': os.getenv('SCIMMA_CREDENTIAL_USERNAME',
#                                          'set SCIMMA_CREDENTIAL_USERNAME value in environment'),
#         'CREDENTIAL_PASSWORD': os.getenv('SCIMMA_CREDENTIAL_PASSWORD',
#                                          'set SCIMMA_CREDENTIAL_PASSWORD value in environment'),
#         'USER_TOPICS': ['hermes.test', 'tomtoolkit.test']
#     },
#     'tom-demo-dev': {
#         'DISPLAY_NAME': os.getenv('TOM_DEMO_DISPLAY_NAME', 'TOM Demo Dev'),
#         'BASE_URL': os.getenv('TOM_DEMO_BASE_URL', 'http://tom-demo-dev.lco.gtn/'),
#         'USERNAME': os.getenv('TOM_DEMO_USERNAME', 'set TOM_DEMO_USERNAME value in environment'),
#         'PASSWORD': os.getenv('TOM_DEMO_PASSWORD', 'set TOM_DEMO_PASSWORD value in environment'),
#     },
#     'localhost-tom': {
#         # for testing; share with yourself
#         'DISPLAY_NAME': os.getenv('LOCALHOST_TOM_DISPLAY_NAME', 'Local'),
#         'BASE_URL': os.getenv('LOCALHOST_TOM_BASE_URL', 'http://127.0.0.1:8000/'),
#         'USERNAME': os.getenv('LOCALHOST_TOM_USERNAME', 'set LOCALHOST_TOM_USERNAME value in environment'),
#         'PASSWORD': os.getenv('LOCALHOST_TOM_PASSWORD', 'set LOCALHOST_TOM_PASSWORD value in environment'),
#     }
# }

TOM_CADENCE_STRATEGIES = [
    'tom_observations.cadences.retry_failed_observations.RetryFailedObservationsStrategy',
    'tom_observations.cadences.resume_cadence_after_failure.ResumeCadenceAfterFailureStrategy'
]

# Define extra target fields here. Types can be any of "number", "string", "boolean" or "datetime"
# See https://tomtoolkit.github.io/docs/target_fields for documentation on this feature
# For example:
# EXTRA_FIELDS = [
#     {'name': 'redshift', 'type': 'number', 'default': 0},
#     {'name': 'discoverer', 'type': 'string'},
#     {'name': 'eligible', 'type': 'boolean', 'hidden': True},
#     {'name': 'discovery_date', 'type': 'datetime'}
# ]
EXTRA_FIELDS = []

# Define custom DataProcessor class
# DATA_PROCESSOR_CLASS = 'mytom.custom_data_processor.CustomDataProcessor'

# Authentication strategy can either be LOCKED (required login for all views)
# or READ_ONLY (read only access to views)
AUTH_STRATEGY = 'READ_ONLY'

# Row-level data permissions restrict users from viewing certain objects unless they are a member of the group to which
# the object belongs. Setting this value to True will allow all `ObservationRecord`, `DataProduct`, and `ReducedDatum`
# objects to be seen by everyone. Setting it to False will allow users to specify which groups can access
# `ObservationRecord`, `DataProduct`, and `ReducedDatum` objects.
TARGET_PERMISSIONS_ONLY = True

# URLs that should be allowed access even with AUTH_STRATEGY = LOCKED
# for example: OPEN_URLS = ['/', '/about']
OPEN_URLS = []

HOOKS = {
    'target_post_save': 'tom_common.hooks.target_post_save',
    'observation_change_state': 'tom_common.hooks.observation_change_state',
    'data_product_post_upload': 'tom_dataproducts.hooks.data_product_post_upload'
}

AUTO_THUMBNAILS = False

THUMBNAIL_MAX_SIZE = (0, 0)

THUMBNAIL_DEFAULT_SIZE = (200, 200)

HINTS_ENABLED = False
HINT_LEVEL = 20

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
    ],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100
}

try:
    from local_settings import *  # noqa
except ImportError:
    pass
