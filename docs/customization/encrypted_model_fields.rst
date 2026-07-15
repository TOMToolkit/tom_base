Encrypted Model Fields
======================

If your ``custom_code`` or reusable app needs to store a secret (e.g. an API key
or password for an external service) — TOM Toolkit provides
:class:`~tom_common.encryption.EncryptedModelField`, a model field that
encrypts its value as it is stored in the database.

.. note::

   Encryption protects the secret from passive database exposure. It does
   **not** protect it from anyone who can read your TOM's ``settings.SECRET_KEY``
   (such as a server administrator). See :doc:`/deployment/encryption` for the
   encryption documentation relevant to TOM administrators.

This page describes how to add an encrypted field to a user-profile model,
how to display it, and how to edit it. Working examples live in
`tom_hermes <https://github.com/TOMToolkit/tom_hermes>`__,
`tom_eso <https://github.com/TOMToolkit/tom_eso>`__,
`tom_swift <https://github.com/TOMToolkit/tom_swift>`__, and
`tom_demoapp <https://github.com/TOMToolkit/tom_demoapp>`__.

Adding an EncryptedModelField
-------------------------------

Declare an :class:`~tom_common.encryption.EncryptedModelField` on your model:

.. code-block:: python
    :caption: models.py

    from django.conf import settings
    from django.db import models

    from tom_common.encryption import EncryptedModelField


    class MyAppProfile(models.Model):
        user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
        api_key = EncryptedModelField(null=True, blank=True)

Read and write it like any other field; the value is encrypted on save and
decrypted on load:

.. code-block:: python

    profile.api_key = 'something-secret'   # encrypted on save
    profile.save()

    profile.api_key                        # -> 'something-secret' (decrypted on load)

Assigning ``None`` or ``''`` clears the stored value (the column becomes
``NULL``); reading an unset value returns ``None``.

Displaying the value of an encrypted field
-------------------------------------------

To show the value with a click-to-reveal control, use ``tom_common``'s
``revealable_password_input.html`` partial. Pass it the **plaintext**, which
comes from direct attribute access (``profile.api_key``):

.. code-block:: python
    :caption: e.g. an inclusion tag or a view's get_context_data

    context = {'api_key': profile.api_key}  # plaintext becomes part of the template context

.. code-block:: html+django
    :caption: my_template.html

    {% if api_key %}
        {% include 'tom_common/partials/revealable_password_input.html' with value=api_key %}
    {% else %}
        (not set)
    {% endif %}

.. note::

   Pass the plaintext only to templates the current user is allowed to see: the
   partial embeds the plaintext value in the page HTML. Revealing it merely toggles
   its visibility. Do **not** source the value from ``model_to_dict``, a DRF
   serializer, or ``dumpdata`` — those return a ``REDACTED`` placeholder for
   encrypted fields, never the secret. (If a profile card auto-iterates fields
   with ``model_to_dict``, exclude the encrypted one and add ``profile.api_key``
   back explicitly.)

Editing the value in an UpdateView
-----------------------------------

List the field on a ``ModelForm``-based view. It renders as a masked input
paired with a **Clear** checkbox:

.. code-block:: python

    class MyProfileUpdateView(UpdateView):
        model = MyAppProfile
        fields = ['api_key']

On submitting the update form, an EncryptedModelField has the following behavior:

- a new, typed-in value replaces the stored one;
- a **blank** input keeps the stored value — so editing other fields on the
  same form never wipes the secret;
- Checking the **Clear** checkbox with a blank input removes the current value (column becomes ``NULL``);
- a typed-in value together with **Clear** keeps the typed value (Clear is ignored).

The form never renders the stored value, so it can't leak through the edit
page. The placeholder text displayed in the input box signals the current state
— ``(A stored value is hidden) — type to replace`` versus ``(not set) — type to add``.

How it works (implementation details)
-------------------------------------

Each value is encrypted with a Fernet cipher derived from
``settings.SECRET_KEY`` (via a key derivation function, :ref:`HKDF <kdf-implementation-details>`).
Decryption also tries any ``settings.SECRET_KEY_FALLBACKS``, facilitating key rotation —
see :doc:`/deployment/encryption` for the procedure and the ``rotate_encryption_key`` command.

If a stored value cannot be decrypted under any active key, reading it raises
``cryptography.fernet.InvalidToken`` — usually because a key was dropped from
the rotation set before its data was re-encrypted.

Limitations
-----------

- **No filtering.** Fernet ciphertext is non-deterministic, so equality lookups
  can never match; ``MyAppProfile.objects.filter(api_key=...)`` raises
  ``FieldError``. For a searchable secret, store a companion HMAC hash column
  and query that.

API reference
-------------

:class:`~tom_common.encryption.EncryptedModelField` (`source <https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/encryption.py>`__)
    A ``models.BinaryField`` subclass that encrypts on save and decrypts on
    load. See the class docstring for the full method-level contract.

:class:`~tom_common.encryption.EncryptedFormField` (`source <https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/encryption.py>`__)
    The form-side companion (masked input plus the blank-preserves-existing
    behavior). ``ModelForm`` picks it up automatically via
    :meth:`EncryptedModelField.formfield`.
