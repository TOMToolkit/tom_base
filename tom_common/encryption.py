"""Encryption helpers for protecting sensitive user data at rest.

A single Fernet cipher is derived from ``settings.SECRET_KEY`` via HKDF
with a domain-separator label. There is no per-user key material and no
additional environment variable. See the TOMToolkit Deployment
documentation for the ``SECRET_KEY`` rotation procedure.

Decryption transparently honours ``settings.SECRET_KEY_FALLBACKS`` (the
same Django pattern used by ``signing`` for graceful HMAC-key rotation):
the primary key is tried first, then each fallback in turn. Encryption
always uses the primary key.

Glossary:
  Fernet — symmetric authenticated encryption recipe from the
    ``cryptography`` library: AES-128-CBC for confidentiality plus
    HMAC-SHA256 for integrity, with a versioned, URL-safe token format.
  HMAC — Hash-based Message Authentication Code (RFC 2104); a keyed
    construction used here both inside Fernet (for integrity) and inside
    HKDF (as its core primitive).
  HKDF (RFC 5869) — HMAC-based Key Derivation Function; turns a
    high-entropy secret into one or more independent cryptographic keys.
    Used here to derive the Fernet key from ``SECRET_KEY`` so the same
    secret can also feed Django's signing without key reuse across
    purposes.
  Domain separator — the ``info`` label passed to HKDF
    (``_HKDF_INFO``). Different labels produce independent keys from the
    same input secret, which is what isolates this module's key from any
    other HKDF use of ``SECRET_KEY``.
  SECRET_KEY / SECRET_KEY_FALLBACKS — Django settings holding the
    current signing/encryption secret and an ordered list of retired
    secrets still accepted for verification/decryption during rotation.
"""
from __future__ import annotations

from base64 import urlsafe_b64encode
from typing import Iterable

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from django.conf import settings


# Domain separator for the HKDF derivation. Bump the ``v1`` suffix only on
# an intentional derivation change; existing encrypted data will not
# decrypt under a new label.
_HKDF_INFO = b'tom-toolkit-encryption-v1'


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet-shaped key (URL-safe base64 of 32 bytes) from ``secret``.

    HKDF (RFC 5869) with SHA-256, no salt, and a fixed domain-separator
    label keeps this derivation cryptographically independent from any
    other use of the same ``secret`` (notably Django's HMAC signing of
    cookies and tokens, which also reads ``SECRET_KEY``).
    """
    # Step 1: HKDF operates on bytes, not str, so encode the secret as its
    # input keying material (IKM, in RFC 5869 terminology).
    input_keying_material_bytes = secret.encode()

    # Step 2: Configure HKDF.
    #   algorithm — SHA-256 is the hash underlying HKDF's HMAC extract/expand.
    #   length    — 32 bytes, the raw key size Fernet needs before base64.
    #   salt      — None lets HKDF use an all-zero salt of the hash's block
    #               size; acceptable here because the input is already a
    #               high-entropy Django SECRET_KEY.
    #   info      — the domain-separator label that isolates this derivation
    #               from any other HKDF use of the same SECRET_KEY.
    fernet_raw_key_byte_length = 32
    hkdf_derivation = HKDF(
        algorithm=hashes.SHA256(),
        length=fernet_raw_key_byte_length,
        salt=None,
        info=_HKDF_INFO,
    )

    # Step 3: Run HKDF's extract-then-expand stages to produce the raw key.
    derived_raw_key_bytes = hkdf_derivation.derive(input_keying_material_bytes)

    # Step 4: Fernet's constructor requires the key as URL-safe base64 of
    # 32 bytes, so encode the raw bytes into that format before returning.
    fernet_formatted_key_bytes = urlsafe_b64encode(derived_raw_key_bytes)
    return fernet_formatted_key_bytes


def _get_cipher() -> Fernet:
    """Build the Fernet cipher from the current ``settings.SECRET_KEY``.

    Computed fresh each call rather than cached at import time so that
    Django's ``override_settings`` works in tests without cache-busting.
    HKDF is cheap; Fernet construction dominates only marginally.
    """
    return Fernet(_derive_fernet_key(settings.SECRET_KEY))


def _iter_ciphers() -> Iterable[Fernet]:
    """Yield the primary cipher, then one per ``SECRET_KEY_FALLBACKS`` entry."""
    yield _get_cipher()
    for fallback in getattr(settings, 'SECRET_KEY_FALLBACKS', []):
        yield Fernet(_derive_fernet_key(fallback))


def encrypt(plaintext: str) -> bytes:
    """Encrypt a string under the primary cipher.

    Returns the ciphertext as bytes suitable for storing in a Django
    ``BinaryField``. The primary cipher is derived from the current
    ``settings.SECRET_KEY``; fallback keys are never used for encryption.
    """
    return _get_cipher().encrypt(plaintext.encode())


def decrypt(blob: bytes | memoryview) -> str:
    """Decrypt ciphertext, trying the primary cipher then each fallback.

    Raises ``cryptography.fernet.InvalidToken`` if no key in
    ``SECRET_KEY`` ∪ ``SECRET_KEY_FALLBACKS`` can decrypt the blob —
    that typically means the data was encrypted under a key that has
    since been removed from the rotation set.
    """
    # Django's BinaryField returns different Python types depending on the
    # database backend: SQLite returns ``bytes`` directly, while psycopg
    # (PostgreSQL) returns a ``memoryview``. Fernet's ``decrypt`` accepts
    # only ``bytes``/``str``, so normalise here.
    if isinstance(blob, memoryview):
        blob = blob.tobytes()

    # decrypt using the primary or fallback SECRET_KEY-created cipher
    last_err: Exception | None = None
    for cipher in _iter_ciphers():
        try:
            return cipher.decrypt(blob).decode()
        except InvalidToken as e:
            last_err = e
    raise last_err if last_err is not None else InvalidToken()
