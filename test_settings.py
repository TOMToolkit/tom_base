from tom_base.settings import *  # noqa

DATABASES = {
   'default': {
       'ENGINE': 'django.db.backends.postgresql',
       'NAME': 'tom',
       'USER': 'postgres',
       'PASSWORD': 'postgres',
       'HOST': '127.0.0.1',
       'PORT': 5432
   }
}
