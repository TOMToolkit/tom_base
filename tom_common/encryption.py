"""Encrypted-at-rest data: low-level helpers and Django integration classes.

A single Fernet cipher is derived from ``settings.SECRET_KEY`` via HKDF
(see Glossary below for acryonym definitions) with a domain-separator
label. See the TOMToolkit Deployment documentation for the ``SECRET_KEY``
rotation procedure.

Decryption transparently honours ``settings.SECRET_KEY_FALLBACKS`` (the
same Django pattern used by ``signing`` for graceful HMAC-key rotation):
the primary key is tried first, then each fallback in turn. Encryption
always uses the primary key.

Public surface for application code:

- :func:`encrypt` / :func:`decrypt` — low-level helpers.
- :class:`EncryptedModelField` — ``models.BinaryField`` subclass that
  transparently encrypts strings on save and decrypts on load. The
  preferred way to add an encrypted field to a model.
- :class:`EncryptedFormField` — form-side companion to
  :class:`EncryptedModelField`. Handles the masked-input UX and the
  blank-submission-preserves-existing-value behavior.

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
from typing import Any, Iterable

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from django import forms
from django.conf import settings
from django.core.exceptions import FieldError, ValidationError
from django.db import models
from django.utils.text import capfirst


# Domain separator for the HKDF derivation. Bump the ``v1`` suffix only on
# an intentional derivation change; existing encrypted data will not
# decrypt under a new label.
_HKDF_INFO = b'tom-toolkit-encryption-v1'


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet key (URL-safe base64 of 32 bytes) from ``secret``.

    HKDF (RFC 5869) with SHA-256, no salt, and a fixed domain-separator
    label keeps this derivation cryptographically independent from any
    other use of the same ``secret`` (notably Django's HMAC signing of
    cookies and tokens, which also reads ``SECRET_KEY``).
    """
    # HKDF operates on bytes, not str, so encode the secret as its
    # "input keying material" (IKM, in RFC 5869 terminology).
    input_keying_material_bytes = secret.encode()

    # configure the key derivation function
    fernet_raw_key_byte_length = 32  # length required by Fernet cipher generator
    hkdf_key_derivation = HKDF(
        algorithm=hashes.SHA256(),
        length=fernet_raw_key_byte_length,
        salt=None,  # SECRET_KEY is already high entropy
        info=_HKDF_INFO,
    )

    # apply the key derivation function to produce the raw key.
    derived_raw_key_bytes = hkdf_key_derivation.derive(input_keying_material_bytes)

    # encode the raw bytes
    fernet_formatted_key_bytes = urlsafe_b64encode(derived_raw_key_bytes)
    return fernet_formatted_key_bytes


def _get_cipher() -> Fernet:
    """Build the Fernet cipher from the current ``settings.SECRET_KEY``.

    Computed fresh each call rather than cached at import time so that
    Django's ``override_settings`` works in tests without cache-busting.
    HKDF is cheap; Fernet construction dominates only marginally.
    """
    cipher = Fernet(_derive_fernet_key(settings.SECRET_KEY))
    return cipher


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
    cipher = _get_cipher()
    ciphertext = cipher.encrypt(plaintext.encode())
    return ciphertext


def decrypt(ciphertext: bytes | memoryview) -> str:
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
    if isinstance(ciphertext, memoryview):
        ciphertext = ciphertext.tobytes()

    # decrypt (the loop and exception handling is for the FALLBACK mechanism)
    last_err: Exception | None = None
    for cipher in _iter_ciphers():
        try:
            plaintext = cipher.decrypt(ciphertext).decode()  # decryption happens here
            return plaintext
        except InvalidToken as e:
            last_err = e
    raise last_err if last_err is not None else InvalidToken()


# These flags are private to this module and implement the
# wierd (but standard) logic surrounding editting encrypted values.
# They are object() instances and not magic strings so there
# is no confusion (i.e. that the string is real data).

# This flag is  produced by EncryptedFormField.clean()
# when a blank value is submitted. The flag is detected by
# EncryptedModelField.pre_save, which interprets it as "leave the
# existing ciphertext alone" (rather than overwriting with blank).
_KEEP_EXISTING_VALUE = object()

# This flag is produced by ClearableEncryptedInput when the
# user checks the "Clear stored value" box and submits an empty input.
# EncryptedFormField.clean translates this into None, which routes
# through get_prep_value as NULL storage.
_CLEAR_EXISTING_VALUE = object()


class ClearableEncryptedInput(forms.PasswordInput):
    """Password input rendered alongside a "Clear stored value" checkbox.

    Mirrors Django's :class:`ClearableFileInput` pattern. The form's
    POST data contains two keys: the password value and the checkbox
    state. :meth:`value_from_datadict` composes them into a single
    submitted value:

    - typed password, checkbox state ignored → the typed value
      (an explicit new value wins over a contradictory clear request)
    - empty password, checkbox checked → the :data:`_CLEAR_EXISTING_VALUE` flag
    - empty password, checkbox unchecked → empty string
      (:class:`EncryptedFormField` translates this into
      :data:`_KEEP_EXISTING_VALUE`)
    """

    template_name = 'tom_common/partials/clearable_encrypted_input.html'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Extends :meth:`forms.PasswordInput.__init__` with our default
        render-value and class attribute; everything else is forwarded.

        The placeholder is chosen at render time in :meth:`get_context`
        because it depends on whether a value is currently stored —
        which the widget only knows when ``get_context`` is called.
        """
        # don't render the value
        kwargs.setdefault('render_value', False)

        # add the form-control class so that all the controls
        # (field, clear-checkbox, etc) render together
        kwargs.setdefault('attrs', {'class': 'form-control'})
        super().__init__(*args, **kwargs)

    def clear_checkbox_name(self, name: str) -> str:
        """New helper (not a super-class override).

        Naming convention mirrors Django's
        :meth:`ClearableFileInput.clear_checkbox_name` — the companion
        checkbox key in POST data is the field name suffixed with
        ``-clear``.
        """
        return f'{name}-clear'

    def clear_checkbox_id(self, name: str) -> str:
        """New helper (not a super-class override).

        Naming convention mirrors Django's
        :meth:`ClearableFileInput.clear_checkbox_id` — the companion
        checkbox HTML ``id`` derives from the field name.
        """
        return f'id_{name}-clear'

    def get_context(self, name: str, value: Any, attrs: Any) -> dict:
        """Extends :meth:`forms.Widget.get_context` to
        1. inject the checkbox name and id into the widget template context,
        and 2. set a value-aware placeholder on the input.

        The placeholder reflects whether the bound model instance has a
        stored value. The rendered form communicates the field's
        state without ever putting the stored value into the HTML:

        - truthy ``value`` (stored plaintext from
          ``EncryptedModelField.from_db_value``) → "A stored value is hidden) —
          type to replace"
        - ``None`` / empty / flag-on-re-render → "(not set) —
          type to add"

        A developer-supplied ``placeholder`` in ``attrs`` wins over the
        default.
        """
        # get any context from the parent Widget
        context = super().get_context(name, value, attrs)

        # set a placeholder according to whether a value is stored
        if 'placeholder' not in context['widget']['attrs']:
            if value:
                # A stored value is hidden
                context['widget']['attrs']['placeholder'] = (
                    '(A stored value is hidden) — type to replace'
                )
            else:
                # there is no stored value at the moment
                context['widget']['attrs']['placeholder'] = (
                    '(not set) — type to add'
                )

        # inject the checkbox that allows the user to clear the value (if any)
        context['widget']['checkbox_name'] = self.clear_checkbox_name(name)
        context['widget']['checkbox_id'] = self.clear_checkbox_id(name)
        return context

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        """Overrides :meth:`forms.Widget.value_from_datadict` to compose
        the password input and the companion clear-checkbox into a single
        submitted value. See the class docstring for the precedence rules.
        """
        typed_value = super().value_from_datadict(data, files, name)
        if typed_value:
            # Explicit new value wins over a contradictory clear request.
            return typed_value
        clear_checked = forms.CheckboxInput().value_from_datadict(
            data, files, self.clear_checkbox_name(name)
        )
        if clear_checked:
            return _CLEAR_EXISTING_VALUE
        return typed_value


class EncryptedFormField(forms.CharField):
    """Form-side companion to :class:`EncryptedModelField`.

    NOTE: This class does not perform encryption itself. The actual
    encryption happens in :meth:`EncryptedModelField.get_prep_value`
    at model-save time.

    Default widget is a masked password input that does NOT render the
    existing value (``render_value=False``). An admin opening a change
    form for an instance that already has a secret therefore sees an
    empty masked input rather than the real value displayed as dots.

    Blank-submission behavior
    -------------------------
    A blank submission is treated as "leave the existing secret
    unchanged," not "set the secret to empty." The motivating scenario:
    with the default masked widget, the input renders empty whether or
    not a secret is stored; a user editing an unrelated field on the
    same ModelForm would otherwise silently wipe the stored secret on
    Save.

    The mechanism uses a module-private flag (``_KEEP_EXISTING_VALUE``).
    On a blank submission, :meth:`clean` returns the flag;
    ``ModelForm.save()`` writes the flag onto the instance
    attribute via ``construct_instance``;
    :meth:`EncryptedModelField.pre_save` detects it, performs a one-row
    SELECT to retrieve the existing plaintext (decrypted by
    :meth:`from_db_value` in the normal way), restores the in-memory
    attribute, and returns the plaintext for re-encryption under the
    current primary cipher.

    The trade-off: users cannot clear a secret via a blank form
    submission. Clearing requires an explicit code path,
    e.g. ``instance.api_key = None; instance.save()``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Extends :meth:`forms.CharField.__init__` with our default widget
        and ``required=False``; everything else is forwarded.
        """
        # The composite widget renders the masked input plus a
        # "Clear stored value" checkbox so the user has a way to set
        # the stored value to None through the form.
        kwargs.setdefault('widget', ClearableEncryptedInput())
        # Default to not required: the field's purpose is in-place rotation
        # of an existing secret, and required=True interacts badly with the
        # blank-as-no-change behavior.
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def clean(self, value: Any) -> Any:
        """Overrides :meth:`forms.CharField.clean` to translate the two
        widget-produced flags into the values ``EncryptedModelField``
        understands.

        - ``_CLEAR_EXISTING_VALUE`` (clear checkbox checked) → ``None``, which
          ``EncryptedModelField.get_prep_value`` stores as ``NULL``.
        - empty input (None or '') → ``_KEEP_EXISTING_VALUE``, which
          ``EncryptedModelField.pre_save`` resolves to the existing
          stored value (preserves it).
        - anything else → forwarded to ``CharField.clean`` for normal
          validation.
        """
        if value is _CLEAR_EXISTING_VALUE:
            return None
        if value in (None, ''):
            return _KEEP_EXISTING_VALUE
        return super().clean(value)

    def has_changed(self, initial: Any, data: Any) -> bool:
        """Overrides :meth:`forms.Field.has_changed` to keep
        ``ModelForm.changed_data`` consistent with our :meth:`clean`
        semantics:

        - clear request → counts as a change.
        - blank-as-no-change → not a change.
        - real value → defer to ``CharField.has_changed``.
        """
        if data is _CLEAR_EXISTING_VALUE:
            return True
        if not data:
            return False
        return super().has_changed(initial, data)


class EncryptedModelField(models.BinaryField):
    """A string field whose value is encrypted with the project Fernet cipher.

    Stores the ciphertext in a ``BinaryField`` column. The Python
    interface is ``str``: assigning ``instance.api_key = '...'`` encrypts
    on save; reading ``instance.api_key`` after a load returns the
    decrypted plaintext.

    Example::

        class MyProfile(models.Model):
            user = models.OneToOneField(...)
            api_key = EncryptedModelField(null=True, blank=True)

    Form integration
    ----------------
    :meth:`formfield` returns an :class:`EncryptedFormField` by default
    — see that class for the masked-input UX and the
    blank-submission-preserves-existing-value behavior.

    Lookups
    -------
    Filtering on encrypted columns is not supported.
    :meth:`get_lookup` raises ``FieldError`` rather than silently
    returning empty querysets.

    Decryption errors
    -----------------
    If a stored ciphertext cannot be decrypted under any active key
    (``settings.SECRET_KEY`` ∪ ``settings.SECRET_KEY_FALLBACKS``),
    :meth:`from_db_value` raises ``cryptography.fernet.InvalidToken``
    at row-load time. The error surfaces when the queryset iterator
    reaches the bad row.
    """
    description = 'Encrypted text'

    # This text is shown until the user click the eye-to-reveal icon
    REDACTED: str = '******** (encrypted, not shown)'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # BinaryField defaults editable=False because why would raw
        # binary data be in a form? However, we want the field to be editable
        # by default. Required for ``modelform_factory`` to create
        # the ModelForm correctly.
        kwargs.setdefault('editable', True)  # edittable BinaryField for reasons above
        super().__init__(*args, **kwargs)

    def from_db_value(self, value: bytes | memoryview | None,
                      expression: Any, connection: Any,) -> str | None:
        """Decrypt on load. Normalises psycopg's ``memoryview`` to ``bytes``.
        """
        if value is None:
            return None

        # sqlite3 and psycopg store BinaryFields differently:
        if isinstance(value, memoryview):
            # this is a psycopg memoryview and must be converted to bytes
            value = value.tobytes()

        plaintext: str = decrypt(value)  # an sqlite BinaryField value is already bytes
        return plaintext

    def to_python(self, value: Any) -> Any:
        """Coerce to the canonical Python type (``str`` or ``None``).

        Invoked by ``Field.clean()`` during model-level ``full_clean``
        (which ``ModelForm._post_clean`` runs after ``construct_instance``)
        and by fixture deserialization. Form-field cleaning does NOT
        flow through this method; :class:`EncryptedFormField` has its
        own ``clean()``.

        The ``_KEEP_EXISTING_VALUE`` flag must pass through untouched —
        otherwise ``Field.clean`` would coerce it to ``str(flag)``
        via the fall-through below, and that string would replace the
        flag on the instance before :meth:`pre_save` ever ran,
        breaking blank-submission preservation.
        """
        if value is None:
            return None
        if value is _KEEP_EXISTING_VALUE:
            return value
        if isinstance(value, str):
            # we're expecting an actual value, not the **** placeholder text
            if value == self.REDACTED:
                # oh no! we somehow got the **** placeholder text!
                # so fail loudly rather than encrypting the placeholder as
                # the new value.
                raise ValidationError(
                    f'Refusing to deserialize the redaction placeholder '
                    f'{self.REDACTED!r}. EncryptedModelField does not '
                    f'support dumpdata/loaddata round-trips: serialization '
                    f'paths emit only the placeholder, not the secret.'
                )
            return value

        # this is more psycopg vs sqlite logic
        if isinstance(value, (bytes, memoryview)):
            raw = value if isinstance(value, bytes) else value.tobytes()
            return decrypt(raw)

        return str(value)

    def get_prep_value(self, value: Any) -> bytes | None:
        """Prepare a Python value for database storage — i.e. encrypt it.

        Q: Why the wierd method name?
        A: ``get_prep_value`` is Django's standard Field override hook
        (the name is fixed by the framework) for converting a Python
        attribute value into the form the database expects. For an
        EncryptedModelField, that conversion is encryption.

        Treats ``None`` and ``''`` identically as "no value" (stored as
        ``NULL``), so a caller writing ``instance.api_key = ''`` instead
        of ``= None`` doesn't end up with an encrypted empty string.

        Defensive guard: the ``_KEEP_EXISTING_VALUE`` flag must never reach
        ``encrypt()`` — that would persist the object's string repr.
        Under normal flow, :meth:`pre_save` resolves the flag before
        this method runs; this guard backstops any path that bypasses
        ``pre_save``.
        """
        if value is None or value == '' or value is _KEEP_EXISTING_VALUE:
            return None
        return encrypt(str(value))

    def pre_save(self, model_instance: models.Model, add: bool) -> Any:
        """Resolve the blank-preservation flag from EncryptedFormField.

        When a ModelForm submits blank for an EncryptedFormField, the
        flag ``_KEEP_EXISTING_VALUE`` flows through ``cleaned_data`` and
        is set on the instance attribute by ``construct_instance``. We
        intercept it here, fetch the existing plaintext (one-row SELECT,
        decrypted by :meth:`from_db_value` along the way), restore the
        in-memory attribute, and return the plaintext for the normal
        encryption pipeline. Net effect: the secret is preserved
        (re-encrypted under the current primary cipher, which is fine
        — the plaintext is unchanged).
        """
        value = getattr(model_instance, self.attname)
        if value is _KEEP_EXISTING_VALUE:
            if add:
                # New instance — there is no existing value to preserve.
                value = None
            else:
                value = (
                    type(model_instance)
                    ._default_manager
                    .filter(pk=model_instance.pk)
                    .values_list(self.attname, flat=True)
                    .first()
                )
            # Sync the in-memory state so post-save reads return the
            # plaintext, not the flag.
            setattr(model_instance, self.attname, value)
        return value

    def formfield(self, **kwargs: Any) -> forms.Field:
        """Return an :class:`EncryptedFormField` for ``ModelForm`` integration.

        Overrides ``BinaryField.formfield``, which returns ``None``
        because (normally) raw binary data is not editable in a regular form.
        """
        defaults: dict[str, Any] = {
            'form_class': EncryptedFormField,
            'required': not self.blank,
            'label': capfirst(self.verbose_name),
            'help_text': self.help_text,
        }
        defaults.update(kwargs)
        form_class = defaults.pop('form_class')
        return form_class(**defaults)

    def get_lookup(self, lookup_name: str) -> Any:
        """Refuse all lookups — Fernet ciphertext cannot match a plaintext query.

        Raised on any ``.filter()``, ``.exclude()``, ``.get()``, etc.
        that targets this column.
        """
        raise FieldError(
            f'{type(self).__name__} does not support the {lookup_name!r} '
            f'lookup. Fernet encryption is non-deterministic, so the same '
            f'plaintext encrypts to different ciphertext each time and '
            f'database-level equality cannot match. If you need equality '
            f'search on this value, store a companion HMAC-derived hash '
            f'column alongside.'
        )

    def value_from_object(self, obj: models.Model) -> str | None:
        """Return the :attr:`REDACTED` placeholder, never the plaintext.

        Called by DRF's default ``ModelSerializer`` field-value
        discovery and by admin display introspection. Direct attribute
        access (``getattr(instance, field_name)``) bypasses this method
        and returns plaintext — that is the intended escape hatch.
        """
        if obj.__dict__.get(self.attname):
            return self.REDACTED
        return None

    def value_to_string(self, obj: models.Model) -> str:
        """Return the :attr:`REDACTED` placeholder for ``dumpdata`` output."""
        return self.REDACTED if obj.__dict__.get(self.attname) else ''
