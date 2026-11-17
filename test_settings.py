from tom_base.settings import *  # noqa

# Speed up password hashing for tests only, NEVER use this in production!
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Per-process cache, so tests running under --parallel don't share the file-based cache in /tmp
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
