Encrypted Model Fields
======================

If your ``custom_code`` or reusable app contains a model field storing
user-specific sensitive data, TOM Toolkit provides a way to encrypt
that data in the database.

Examples of user-specific sensitive data include passwords or API keys
for external services that your TOM stores on the user's behalf. TOM
Toolkit's Facility modules, for example, use the mechanism described
here to store user-specific external-service credentials in a user
profile model. Real examples live in
`tom_eso <https://github.com/TOMToolkit/tom_eso>`__ and
`tom_swift <https://github.com/TOMToolkit/tom_swift>`__.

How encryption works
--------------------

Encrypted fields are protected by a single Fernet cipher derived from
``settings.SECRET_KEY``. For TOM administrator concerns (rotating
``SECRET_KEY`` without losing data, etc.) see
:doc:`/deployment/encryption`.

.. note::

   Encryption protects data from passive database exposure. It does NOT
   protect against a server administrator with access to the
   ``settings.SECRET_KEY``. If you need user-level isolation from
   administrators, the toolkit's current scheme is not sufficient.

Adding an encrypted field to a model
------------------------------------

Declare an :class:`~tom_common.encryption.EncryptedModelField` alongside
your other model fields:

.. code-block:: python

    from django.db import models
    from tom_common.encryption import EncryptedModelField


    class MyAppProfile(models.Model):
        # you probably have a user OneToOneField here
        api_key = EncryptedModelField(null=True, blank=True)

That single declaration replaces the older
``BinaryField + EncryptedProperty`` pair. The underlying database
column is still binary (it holds the ciphertext bytes), but Django
sees ``api_key`` as one normal named field — ``ModelForm``, the admin,
DRF ``ModelSerializer``, and ``dumpdata`` all introspect it without
any extra glue.

Reading and writing the value in code
-------------------------------------

Access the field like any other Python attribute. The field handles
encryption on save and decryption on load:

.. code-block:: python

    profile.api_key = 'something-secret'
    profile.save()

    # later, possibly in a different process / request:
    value = profile.api_key   # 'something-secret'

Assigning ``None`` or the empty string ``''`` clears the stored value
(column stored as ``NULL``). Reading an unset value yields ``None``.

Editing the value through a ModelForm
-------------------------------------

A ``ModelForm`` with ``fields = [..., 'api_key']`` (or
``fields = '__all__'``) renders ``api_key`` automatically using the
:class:`~tom_common.encryption.EncryptedFormField` returned by
:meth:`EncryptedModelField.formfield`. The default widget is a masked
password input that does NOT render the existing value, so an admin
opening a change form sees an empty input rather than the real secret
displayed as dots.

Blank-submission behavior
~~~~~~~~~~~~~~~~~~~~~~~~~

A blank submission preserves the existing stored value. The motivating
scenario: an admin opens the change form to edit an unrelated field,
leaves the masked secret input blank, and clicks Save. Without this
behavior, the stored secret would be silently wiped because the
default masked widget renders empty regardless of whether a value is
stored.

A consequence: *users cannot clear a secret by submitting a blank
form.* Clearing requires an explicit code path:

.. code-block:: python

    profile.api_key = None
    profile.save()

Displaying an encrypted field to the user
-----------------------------------------

For read-only display of a stored secret with a user-driven reveal
control (the "click the eye icon to see the value" pattern), use
``tom_common``'s ``revealable_password_input.html`` partial template.

Add the following to your template where ``password_value`` is the
plaintext value read from the model attribute (e.g.
``profile.api_key``):

.. code-block:: html+django

    {% include 'tom_common/partials/revealable_password_input.html' with value=password_value %}

The partial renders a masked input of fixed length; the real value is
only injected into the DOM when the user clicks the reveal icon.

What you cannot do with an EncryptedModelField
----------------------------------------------

**Filter on the value.** Fernet is non-deterministic — every
``encrypt()`` produces a different ciphertext for the same plaintext,
so database-level equality lookups can never match.
:meth:`EncryptedModelField.get_lookup` raises ``FieldError`` rather
than silently returning empty querysets:

.. code-block:: python

    MyAppProfile.objects.filter(api_key='foo')   # raises FieldError

If you need equality search on the encrypted column, store a
companion HMAC-derived hash column alongside it and query the hash.

**Round-trip via dumpdata / loaddata.** Serialization paths emit a
placeholder (``EncryptedModelField.REDACTED``, currently
``'******** (encrypted, not shown)'``) rather than the plaintext.
This keeps secrets out of fixture files, DRF API responses, and
admin history by default. As a consequence, attempting to load a
``dumpdata`` fixture back fails loudly when
:meth:`~EncryptedModelField.to_python` encounters the placeholder.
To migrate encrypted data between environments, copy the database
row directly (the ciphertext survives) or write a one-off
decrypt-and-re-encrypt script.

Direct attribute access (``getattr(instance, field_name)``) bypasses
the redaction and remains the only path to the plaintext — code that
legitimately needs the secret reads the attribute directly.

What happens on decryption failure
----------------------------------

If a stored ciphertext cannot be decrypted under any active key
(``settings.SECRET_KEY`` plus any ``settings.SECRET_KEY_FALLBACKS``),
:meth:`EncryptedModelField.from_db_value` raises
``cryptography.fernet.InvalidToken`` at row-load time. The most
common cause is a key removed from the rotation set before its data
was re-encrypted under a new primary. See
:doc:`/deployment/encryption` for the rotation procedure and the
``rotate_encryption_key`` management command.

API reference
-------------

:class:`~tom_common.encryption.EncryptedModelField` (`source <https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/encryption.py>`__)
    A ``models.BinaryField`` subclass that transparently encrypts on
    save and decrypts on load. See the class docstring in
    ``tom_common/encryption.py`` for the full method-level contract.

:class:`~tom_common.encryption.EncryptedFormField` (`source <https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/encryption.py>`__)
    The form-side companion. Handles the masked-input UX and the
    blank-submission-preserves-existing behavior. ``ModelForm`` picks
    it up automatically via :meth:`EncryptedModelField.formfield`.
