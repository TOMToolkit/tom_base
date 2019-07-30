from tom_base.settings import *  # noqa

DATABASES = {
   'default': {
       'ENGINE': 'django.db.backends.postgresql',
       'NAME': 'tom_pg',
       'USER': 'aye',
       'PASSWORD': 'asdfghjkl',
       'HOST': '127.0.0.1',
       'PORT': 5432
   }
}
