"""Models for TOM Toolkit's user profiles and encrypted field storage.

Encryption Architecture
-----------------------
TOM Toolkit uses envelope encryption to protect sensitive user data (API keys,
observatory credentials) at rest in the database. The scheme has two layers:

1. A server-side **master key** (``TOMTOOLKIT_FIELD_ENCRYPTION_KEY``) is stored in the
   environment, never in the database. It is a Fernet key used to encrypt
   per-user keys.

2. Each user has a random **Data Encryption Key (DEK)** that encrypts their
   actual data. The DEK is stored on the user's ``Profile`` as ``encrypted_dek``
   — encrypted by the master key. To use it, we decrypt it with the master
   key, create a Fernet cipher, and use that cipher to encrypt or decrypt
   individual fields.

This means database access alone cannot decrypt user data — an attacker also
needs the master key from the server environment. See
``docs/design/encryption_architecture_redesign.md`` for the full design.

Plugin developers use ``EncryptedProperty`` descriptors and
``EncryptableModelMixin`` to add encrypted fields to their models, and the
helper functions in ``session_utils`` to read/write those fields. The
encryption plumbing is handled transparently.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User


logger = logging.getLogger(__name__)


class Profile(models.Model):
    """Profile model for a TOMToolkit User.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    # The user's Data Encryption Key (DEK), encrypted by the master key.
    # This is a Fernet-encrypted blob of the user's random DEK. It can only be
    # decrypted using TOMTOOLKIT_FIELD_ENCRYPTION_KEY from the server environment.
    # Null means no DEK has been generated yet (e.g., pre-existing users before
    # this feature was added).
    encrypted_dek = models.BinaryField(null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.user.username} Profile'


class EncryptedProperty:
    """A Python descriptor that provides transparent encryption and decryption
    for a model field.

    This descriptor works with ``EncryptableModelMixin`` and the helper
    functions in ``session_utils``. It expects a Fernet cipher to be
    temporarily attached to the model instance as ``_cipher`` before the
    property is read or written. The cipher is created from the user's
    decrypted DEK by the helper functions and removed immediately after use.

    The ``_cipher`` attachment pattern exists because Python descriptors cannot
    accept extra arguments — the cipher must be passed through the instance.
    Direct access without a cipher raises ``AttributeError`` to prevent
    accidental plaintext reads of encrypted data.

    Usage::

        class MyModel(EncryptableModelMixin, models.Model):
            _my_secret_encrypted = models.BinaryField(null=True)
            my_secret = EncryptedProperty('_my_secret_encrypted')
    """
    def __init__(self, db_field_name: str):
        self.db_field_name = db_field_name
        self.property_name: str | None = None  # Set by __set_name__

    def __set_name__(self, owner: type, name: str) -> None:
        self.property_name = name

    def __get__(self, instance: models.Model | None, owner: type) -> str | EncryptedProperty:
        if instance is None:
            return self

        cipher = getattr(instance, '_cipher', None)
        if not isinstance(cipher, Fernet):
            raise AttributeError(
                f"A Fernet cipher must be set on the '{owner.__name__}' instance "
                f"as '_cipher' to access property '{self.property_name}'. "
                f"Please use session_utils.get_encrypted_field() instead of direct access."
            )

        encrypted_value = getattr(instance, self.db_field_name)
        if not encrypted_value:
            return ''

        # Handle bytes (sqlite3) vs memoryview (postgresql).
        # PostgreSQL/psycopg returns memoryview for BinaryFields;
        # SQLite returns bytes. Fernet.decrypt() needs bytes.
        if isinstance(encrypted_value, memoryview):
            encrypted_value = encrypted_value.tobytes()

        return cipher.decrypt(encrypted_value).decode()

    def __set__(self, instance: models.Model, value: str) -> None:
        cipher = getattr(instance, '_cipher', None)
        if not isinstance(cipher, Fernet):
            raise AttributeError(
                f"A Fernet cipher must be set on the '{instance.__class__.__name__}' instance "
                f"as '_cipher' to set property '{self.property_name}'."
            )

        if not value:
            encrypted_value = None
        else:
            encrypted_value = cipher.encrypt(str(value).encode())

        setattr(instance, self.db_field_name, encrypted_value)


class EncryptableModelMixin(models.Model):
    """A mixin for models that use ``EncryptedProperty`` to handle sensitive data.

    Any model that stores encrypted fields should inherit from this mixin.
    It provides:

    - A standardized ``user`` OneToOneField so that utility functions can
      always find the user associated with an encryptable model instance.
    - A ``clear_encrypted_fields()`` method to null out all encrypted fields
      (used when a user's DEK must be regenerated).

    Subclasses should not redefine the ``user`` field.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def clear_encrypted_fields(self) -> None:
        """Clear all fields managed by an ``EncryptedProperty`` descriptor.

        Sets each encrypted BinaryField to None and saves the model. This is a
        destructive operation — the encrypted data is permanently lost.
        """
        model_save_needed = False
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            if isinstance(attr, EncryptedProperty):
                # Set the underlying BinaryField directly to None, bypassing
                # the descriptor (which would require a cipher).
                setattr(self, attr.db_field_name, None)
                model_save_needed = True
                logger.info(f"Cleared encrypted property '{attr_name}' for {self.__class__.__name__} "
                            f"instance {getattr(self, 'pk', 'UnknownPK')}.")
        if model_save_needed:
            self.save()

    class Meta:
        abstract = True
