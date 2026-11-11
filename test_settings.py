from tom_base.settings import *  # noqa

# Speed up password hashing for tests only, NEVER use this in production!
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
