"""Utilities for encrypting and decrypting sensitive user data at rest.

This module implements the "read/write time" portion of TOM Toolkit's envelope
encryption scheme. The full architecture is documented in
``docs/design/encryption_architecture_redesign.md``; here is a brief summary
of how the pieces fit together:

**Master key** (``TOMTOOLKIT_FIELD_ENCRYPTION_KEY`` in settings / environment):
    A Fernet key that never touches the database. It wraps (encrypts) each
    user's Data Encryption Key so that database access alone cannot reveal
    user data.

**Per-user DEK** (``Profile.wrapped_dek``):
    A random Fernet key generated when the user is created. Stored in the
    database encrypted by the master key. To use it, we unwrap it with the
    master key, build a Fernet cipher, and attach it briefly to the model
    instance that holds the encrypted field.

**EncryptedProperty / EncryptableModelMixin** (in ``models.py``):
    The descriptor and mixin that plugin models use to declare encrypted
    fields. They expect a ``_cipher`` attribute on the model instance —
    this module's helper functions manage that lifecycle.

Typical call from a view or API endpoint::

    from tom_common.session_utils import get_encrypted_field, set_encrypted_field

    api_key = get_encrypted_field(user, eso_profile, 'api_key')
    set_encrypted_field(user, eso_profile, 'api_key', new_value)
    eso_profile.save()
"""

from __future__ import annotations

import logging
from typing import Optional, TypeVar

from cryptography.fernet import Fernet

from django.conf import settings
from django.db import models

from tom_common.models import Profile


logger = logging.getLogger(__name__)

# A generic TypeVar for a Django models.Model subclass instance.
# The `bound=models.Model` constraint ensures that any
# type used for ModelType must be a subclass of `models.Model`.
ModelType = TypeVar('ModelType', bound=models.Model)


def _get_master_cipher() -> Fernet:
    """Return a Fernet cipher built from the server-side master key.

    The master key (``TOMTOOLKIT_FIELD_ENCRYPTION_KEY``) lives in the server
    environment, not in the database. It is used only to wrap and unwrap
    per-user DEKs — never to encrypt user data directly.

    Raises:
        django.core.exceptions.ImproperlyConfigured: If the setting is missing
            or empty.
    """
    key = getattr(settings, 'TOMTOOLKIT_FIELD_ENCRYPTION_KEY', '')
    if not key:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "TOMTOOLKIT_FIELD_ENCRYPTION_KEY is not set. This setting is required for "
            "encrypting sensitive user data at rest. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "Then add it to your environment or settings.py."
        )
    # The key may be a string (from os.getenv) or bytes; Fernet accepts both.
    return Fernet(key)


def create_encrypted_dek() -> bytes:
    """Generate a new random DEK and return it wrapped (encrypted) by the master key.

    This is called once per user, at user-creation time (see ``signals.py``).
    The returned bytes are stored in ``Profile.wrapped_dek``.

    We use ``Fernet.generate_key()`` rather than ``os.urandom()`` because
    Fernet keys have a specific format (URL-safe base64-encoded 32 bytes)
    and ``generate_key()`` guarantees that format.

    Returns:
        The DEK encrypted by the master key, as bytes suitable for a BinaryField.
    """
    # Generate a fresh random Fernet key for this user
    dek: bytes = Fernet.generate_key()
    # Wrap (encrypt) the DEK with the master key so it can be stored safely
    # in the database. The master key is the only thing that can unwrap it.
    master_cipher = _get_master_cipher()
    wrapped_dek: bytes = master_cipher.encrypt(dek)
    return wrapped_dek


def _unwrap_dek(wrapped_dek: bytes) -> bytes:
    """Unwrap (decrypt) a user's DEK using the master key.

    Args:
        wrapped_dek: The encrypted DEK from ``Profile.wrapped_dek``.

    Returns:
        The plaintext DEK (a valid Fernet key as bytes).
    """
    # Handle memoryview from PostgreSQL BinaryField
    if isinstance(wrapped_dek, memoryview):
        wrapped_dek = wrapped_dek.tobytes()

    master_cipher = _get_master_cipher()
    return master_cipher.decrypt(wrapped_dek)


def _get_cipher_for_user(user) -> Fernet:
    """Build a Fernet cipher from a user's unwrapped DEK.

    This fetches the user's ``Profile.wrapped_dek``, unwraps it with the master
    key, and returns a Fernet cipher ready to encrypt or decrypt the user's
    data fields.

    The unwrapped DEK exists only in memory for the duration of this call and
    the subsequent encrypt/decrypt operation. It is never persisted in
    plaintext.

    Args:
        user: A Django User instance.

    Returns:
        A Fernet cipher built from the user's DEK.

    Raises:
        Profile.DoesNotExist: If the user has no Profile.
        ValueError: If the user's Profile has no wrapped DEK.
    """
    profile = Profile.objects.get(user=user)
    if not profile.encrypted_dek:
        raise ValueError(f"User {user.username} has no encryption key (wrapped_dek is empty). "
                         f"This may indicate the user was created before encryption was configured.")

    dek: bytes = _unwrap_dek(profile.encrypted_dek)
    return Fernet(dek)


def get_encrypted_field(user,
                        model_instance: ModelType,
                        field_name: str) -> Optional[str]:
    """Safely get the decrypted value of an EncryptedProperty.

    Fetches the user's DEK from their Profile, unwraps it with the master key,
    creates a Fernet cipher, and uses the ``EncryptedProperty`` descriptor to
    decrypt the field value.

    Args:
        user: The User object associated with the encrypted data.
        model_instance: The model instance containing the EncryptedProperty.
        field_name: The string name of the EncryptedProperty to access.

    Returns:
        The decrypted string value, or None if decryption fails for any reason
        (e.g., no Profile, no DEK, corrupted data).
    """
    try:
        cipher = _get_cipher_for_user(user)
        # Attach the cipher so the EncryptedProperty descriptor can use it,
        # read the decrypted value, then clean up. The cipher is attached to
        # the model instance (not the user) because the descriptor's __get__
        # method receives the instance it's defined on.
        model_instance._cipher = cipher  # type: ignore[attr-defined]
        decrypted_value = getattr(model_instance, field_name)
        return decrypted_value
    except (Profile.DoesNotExist, ValueError) as e:
        logger.warning(f"Could not get encryption key for user {user.username} to access "
                       f"'{field_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while decrypting field '{field_name}' "
                     f"for user {user.username}: {e}")
        return None
    finally:
        # Always remove the temporary cipher from the instance to avoid
        # accidental reuse or leaking the key in memory longer than needed.
        if hasattr(model_instance, '_cipher'):
            del model_instance._cipher  # type: ignore[attr-defined]


def set_encrypted_field(user,
                        model_instance: ModelType,
                        field_name: str,
                        value: str) -> bool:
    """Safely set the value of an EncryptedProperty.

    Fetches the user's DEK, creates a cipher, and uses the
    ``EncryptedProperty`` descriptor to encrypt and store the value.

    Note: This function does NOT save the instance. The caller is responsible
    for calling ``instance.save()`` after the field has been set.

    Args:
        user: The User object associated with the encrypted data.
        model_instance: The model instance containing the EncryptedProperty.
        field_name: The string name of the EncryptedProperty to set.
        value: The plaintext string value to encrypt and set.

    Returns:
        True if the field was set successfully, False otherwise.
    """
    try:
        cipher = _get_cipher_for_user(user)
        model_instance._cipher = cipher  # type: ignore[attr-defined]
        setattr(model_instance, field_name, value)
        return True
    except (Profile.DoesNotExist, ValueError) as e:
        logger.error(f"Could not get encryption key for user {user.username} to set "
                     f"'{field_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while encrypting field '{field_name}' "
                     f"for user {user.username}: {e}")
        return False
    finally:
        if hasattr(model_instance, '_cipher'):
            del model_instance._cipher  # type: ignore[attr-defined]
