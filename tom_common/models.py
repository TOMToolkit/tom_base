"""Models for TOM Toolkit's user profiles and encrypted field storage.

Encryption
----------
Plugin models that hold sensitive per-user data (API keys, observatory
credentials) declare a ``BinaryField`` plus an :class:`EncryptedProperty`
descriptor pointing at it. Reading the property decrypts; writing
encrypts. The cipher is a single Fernet derived from
``settings.SECRET_KEY`` in :mod:`tom_common.encryption`. See
``docs/customization/encrypted_model_fields.rst`` for the plugin-developer
walkthrough.
"""

from __future__ import annotations

import logging

from django.db import models
from django.contrib.auth.models import User


logger = logging.getLogger(__name__)


class Profile(models.Model):
    """Profile model for a TOMToolkit User.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.user.username} Profile'


class EncryptedProperty:
    """A Python descriptor providing transparent encrypt-on-write and
    decrypt-on-read for a sibling :class:`BinaryField`.

    Usage on a plugin model::

        class MyModel(models.Model):
            user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                        on_delete=models.CASCADE)
            _api_key_encrypted = models.BinaryField(null=True, blank=True)
            api_key = EncryptedProperty('_api_key_encrypted')

    Then ``instance.api_key`` and ``instance.api_key = '...'`` work the
    way you'd expect; the underlying ``_api_key_encrypted`` BinaryField
    holds the ciphertext bytes. By convention, the ciphertext field
    starts with an underscore.

    The cipher comes from :func:`tom_common.encryption._get_cipher`
    (imported lazily inside ``__get__``/``__set__`` to avoid a circular
    import). Decryption transparently honours
    ``settings.SECRET_KEY_FALLBACKS`` — see
    :mod:`tom_common.encryption`.
    """
    def __init__(self, db_field_name: str):
        self.db_field_name = db_field_name
        self.property_name: str | None = None  # Set by __set_name__

    def __set_name__(self, owner: type, name: str) -> None:
        self.property_name = name

    def __get__(self, instance: models.Model | None, owner: type) -> str | EncryptedProperty:
        if instance is None:
            return self
        # Local import: tom_common.encryption is not safe to import at
        # module load (the descriptor is referenced before encryption's
        # settings access can succeed in some test paths).
        from tom_common.encryption import decrypt

        encrypted_value = getattr(instance, self.db_field_name)
        if not encrypted_value:
            return ''
        return decrypt(encrypted_value)

    def __set__(self, instance: models.Model, value: str) -> None:
        from tom_common.encryption import encrypt

        if not value:
            encrypted_value = None
        else:
            encrypted_value = encrypt(str(value))
        setattr(instance, self.db_field_name, encrypted_value)
