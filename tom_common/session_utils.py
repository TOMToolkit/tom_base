"""Utilities for encrypting and decrypting sensitive user data at rest.

This module implements the "read/write time" portion of TOM Toolkit's envelope
encryption scheme. The full architecture is documented in
``docs/design/encryption_architecture_redesign.md``; here is a brief summary
of how the pieces fit together:

**Master key** (``TOMTOOLKIT_DEK_ENCRYPTION_KEY`` in settings / environment):
    A Fernet key that never touches the database. It encrypts each user's
    Data Encryption Key so that database access alone cannot reveal user data.

**Per-user DEK** (``Profile.encrypted_dek``):
    A random Fernet key generated when the user is created. Stored in the
    database encrypted by the master key. To use it, we decrypt it with the
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
from dataclasses import dataclass, field
from typing import Optional, TypeVar

from cryptography.fernet import Fernet, InvalidToken

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

    The master key (``TOMTOOLKIT_DEK_ENCRYPTION_KEY``) lives in the server
    environment, not in the database. It is used only to encrypt and decrypt
    per-user DEKs — never to encrypt user data directly.

    Raises:
        django.core.exceptions.ImproperlyConfigured: If the setting is missing
            or empty.
    """
    key = getattr(settings, 'TOMTOOLKIT_DEK_ENCRYPTION_KEY', '')
    if not key:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "TOMTOOLKIT_DEK_ENCRYPTION_KEY is not set. This setting is required for "
            "encrypting sensitive user data at rest. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "Then add it to your environment or settings.py."
        )
    # The key may be a string (from os.getenv) or bytes; Fernet accepts both.
    return Fernet(key)


def create_encrypted_dek() -> bytes:
    """Generate a new random DEK and return it encrypted by the master key.

    This is called once per user, at user-creation time (see ``signals.py``).
    The returned bytes are stored in ``Profile.encrypted_dek``.

    We use ``Fernet.generate_key()`` rather than ``os.urandom()`` because
    Fernet keys have a specific format (URL-safe base64-encoded 32 bytes)
    and ``generate_key()`` guarantees that format.

    Returns:
        The DEK encrypted by the master key, as bytes suitable for a BinaryField.
    """
    # Generate a fresh random Fernet key for this user
    dek: bytes = Fernet.generate_key()
    # Encrypt the DEK with the master key so it can be stored safely
    # in the database. The master key is the only thing that can decrypt it.
    master_cipher = _get_master_cipher()
    encrypted_dek: bytes = master_cipher.encrypt(dek)
    return encrypted_dek


def _decrypt_dek(encrypted_dek: bytes) -> bytes:
    """Decrypt a user's DEK using the master key.

    Args:
        encrypted_dek: The encrypted DEK from ``Profile.encrypted_dek``.

    Returns:
        The plaintext DEK (a valid Fernet key as bytes).
    """
    # Handle memoryview from PostgreSQL BinaryField
    if isinstance(encrypted_dek, memoryview):
        encrypted_dek = encrypted_dek.tobytes()

    master_cipher = _get_master_cipher()
    return master_cipher.decrypt(encrypted_dek)


def _get_cipher_for_user(user) -> Fernet:
    """Build a Fernet cipher from a user's decrypted DEK.

    This fetches the user's ``Profile.encrypted_dek``, decrypts it with the
    master key, and returns a Fernet cipher ready to encrypt or decrypt the
    user's data fields.

    The decrypted DEK exists only in memory for the duration of this call and
    the subsequent encrypt/decrypt operation. It is never persisted in
    plaintext.

    Args:
        user: A Django User instance.

    Returns:
        A Fernet cipher built from the user's DEK.

    Raises:
        Profile.DoesNotExist: If the user has no Profile.
        ValueError: If the user's Profile has no encrypted DEK.
    """
    profile = Profile.objects.get(user=user)
    if not profile.encrypted_dek:
        raise ValueError(f"User {user.username} has no encryption key (encrypted_dek is empty). "
                         f"This may indicate the user was created before encryption was configured.")

    dek: bytes = _decrypt_dek(profile.encrypted_dek)
    return Fernet(dek)


def get_encrypted_field(user,
                        model_instance: ModelType,
                        field_name: str) -> Optional[str]:
    """Safely get the decrypted value of an EncryptedProperty.

    Fetches the user's DEK from their Profile, decrypts it with the master key,
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


# ---------------------------------------------------------------------------
# Master key rotation
# ---------------------------------------------------------------------------

@dataclass
class RotationError:
    """Details about a single Profile that failed during key rotation."""
    profile_pk: int
    username: str
    error: str


@dataclass
class RotationResult:
    """Result of a master key rotation operation.

    Attributes:
        success_count: Number of Profiles whose DEKs were successfully re-encrypted.
        errors: Per-profile details for any that failed.
    """
    success_count: int = 0
    errors: list[RotationError] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def total(self) -> int:
        return self.success_count + self.error_count


def rotate_master_key(new_key: str) -> RotationResult:
    """Re-encrypt all per-user DEKs with a new master key.

    Each Profile's ``encrypted_dek`` is decrypted with the current master key
    (from ``TOMTOOLKIT_DEK_ENCRYPTION_KEY``) and re-encrypted with
    ``new_key``. The user Profile's plaintext DEK is unchanged — only its
    encryption layer (i.e. `encrypted_dek`) is replaced. The actual encrypted
    data is not touched.

    After this function completes successfully, the server's
    ``TOMTOOLKIT_DEK_ENCRYPTION_KEY`` must be updated to ``new_key`` and the
    server restarted. Until that happens, the re-encrypted DEKs cannot be
    decrypted.

    Args:
        new_key: The new Fernet master key as a string (URL-safe base64, 44 chars).

    Returns:
        A ``RotationResult`` with per-profile success/error details.

    Raises:
        ValueError: If ``new_key`` is not a valid Fernet key.
        django.core.exceptions.ImproperlyConfigured: If the current master key
            is missing or empty.
    """
    # Validate the new key before touching any data.
    try:
        new_master_cipher = Fernet(new_key.encode())
    except Exception as e:
        raise ValueError(f"Invalid new key: {e}") from e

    # Build the old master cipher from current settings.
    # Raises ImproperlyConfigured if missing — intentionally not caught here.
    old_master_cipher = _get_master_cipher()

    profiles = Profile.objects.exclude(encrypted_dek=None)
    result = RotationResult()

    for profile in profiles.iterator():
        try:
            encrypted_dek = profile.encrypted_dek
            # Handle memoryview from PostgreSQL
            if isinstance(encrypted_dek, memoryview):
                encrypted_dek = encrypted_dek.tobytes()

            # Decrypt with old key, re-encrypt with new key
            plaintext_dek: bytes = old_master_cipher.decrypt(encrypted_dek)
            new_encrypted_dek: bytes = new_master_cipher.encrypt(plaintext_dek)

            profile.encrypted_dek = new_encrypted_dek
            profile.save(update_fields=['encrypted_dek'])
            result.success_count += 1
        except InvalidToken:
            result.errors.append(RotationError(
                profile_pk=profile.pk,
                username=profile.user.username,
                error="could not decrypt with current master key",
            ))
        except Exception as e:
            result.errors.append(RotationError(
                profile_pk=profile.pk,
                username=profile.user.username,
                error=str(e),
            ))

    return result
