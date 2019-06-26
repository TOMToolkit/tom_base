from tom_base.settings import *  # noqa

DATABASES = {
   'default': {
       'ENGINE': 'django.db.backends.postgresql_psycopg2',
       'NAME': 'tom',
       'USER': 'ixu',
       'PASSWORD': 'irisxu',
       'HOST': '127.0.0.1',
       'PORT': ''
   }
}
