from tom_base.settings import *  # noqa

import multiprocessing
import sys

# workaround to preserve parallel test execution with python 3.14
# Remove once upgraded to Django 6
if sys.platform == "linux":
    multiprocessing.set_start_method("fork", force=True)

# Speed up password hashing for tests only, NEVER use this in production!
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
