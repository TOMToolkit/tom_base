Encrypted Model Fields
======================

If your ``custom_code`` or reusable app needs to store sensitive data
TOM Toolkit provides a way to encrypt that data in the database.

Examples of this type of sensitive data include passwords or API keys
for external services that your TOM stores on the user's behalf. TOM
Toolkit's Facility modules, for example, use the mechanism described
here to store user-specific external-service credentials in a user
profile model. Examples live in
`tom_demoapp <https://github.com/TOMToolkit/tom_demoapp>`__ ,
`tom_eso <https://github.com/TOMToolkit/tom_eso>`__ and
`tom_swift <https://github.com/TOMToolkit/tom_swift>`__.

Quick start
-----------

Here are the steps you'll need to take to add an encrypted field
to a model, display it (from a View subclass) and edit it's value
in a Form and UpdateView subclass:

1. Add an ``EncryptedModelField`` to your model.
2. List the field in your ``UpdateView``'s ``fields``.
3. Pass the plaintext (from the model) to your profile-card template and
   include the ``revealable_password_input.html`` partial.

Each step is covered in its own section below.

Adding an encrypted field to a model
------------------------------------

Declare an :class:`~tom_common.encryption.EncryptedModelField` alongside
your other model fields:

.. code-block:: python

    from django.db import models
    from tom_common.encryption import EncryptedModelField


    class MyAppProfile(models.Model):
        # you probably have a user OneToOneField here as well
        api_key = EncryptedModelField(null=True, blank=True)

The underlying database column is a ``BinaryField`` (it holds
the encrypted ciphertext as bytes). Django sees ``api_key`` as a normal
named field. ``ModelForm``, the Django admin, DRF ``ModelSerializer``, etc
all introspect it appropriately.

Reading and writing the value in code
-------------------------------------

Access the field like any other ``models.Field`` subclass:

.. code-block:: python

    # assignment
    profile.api_key = 'something-secret'
    profile.save()

    # retrieval; later, possibly in a different process / request:
    plaintext_value = profile.api_key   # 'something-secret'


The field handles encryption on save and decryption on load.
Assigning ``None`` or the empty string ``''`` clears the stored value
(column stored as ``NULL``). Reading an unset value yields ``None``.
For implementation details, see ``tom_common/encryption.py``. 

Displaying the current value to your TOM users (read-only)
----------------------------------------------------------

To display an encrypted field value with a user-driven "reveal
control" (i.e. the  "click the eye icon to see the value" pattern),
use ``tom_common``'s ``revealable_password_input.html`` partial template.

The partial needs the **plaintext** as its ``value`` argument, and
plaintext is available via direct attribute access on the model
instance — e.g. ``profile.api_key``. Django introspection paths
(``model_to_dict``, ``ModelSerializer``, ``dumpdata``, admin display)
all go through ``EncryptedModelField.value_from_object``, which
returns the ``REDACTED`` placeholder by design.

In practice, when a profile card uses an inclusion tag (or a view's
``get_context_data``) to provide fields to a template, the encrypted
field has to be excluded from any auto-iteration over the model and
passed in explicitly:

.. code-block:: python

    # exclude the encrypted field from the auto-iteration: model_to_dict
    # would only return the REDACTED placeholder for it
    excluded_fields = ['user', 'id', 'api_key']
    profile_data = model_to_dict(profile, exclude=excluded_fields)
    return {
        'profile_data': profile_data,  # dictionary without the excluded_fields
        'api_key': profile.api_key,   # direct attribute access -> plaintext
    }

Then in the template, render the encrypted field through the partial:

.. code-block:: html+django

    {% if api_key %}
        {% include 'tom_common/partials/revealable_password_input.html' with value=api_key %}
    {% else %}
        (not set)
    {% endif %}

The partial renders a masked input of fixed length; the real value is
only injected into the DOM when the user clicks the reveal icon.

A worked example of this pattern lives in
`tom_demoapp <https://github.com/TOMToolkit/tom_demoapp>`__'s
``demo_extras.py`` and ``profile_demo.html``.

Editing the value in an UpdateView
----------------------------------

Include the ``EncryptedModelField`` in the ``fields`` list of your
``ProfileUpdateView`` (or any other ``ModelForm``-based view) and the
form renders the field automatically as a composite control with:

- a masked password input joined to
- an eye-icon reveal button and
- a "Clear" checkbox

in a single input-group.

.. code-block:: python

    class MyProfileUpdateView(UpdateView):
        model = MyAppProfile
        fields = ['api_key', 'display_name']

How the control behaves on submit:

- A typed value replaces the stored value.
- An empty input leaves the stored value unchanged. This protects
  the secret when a user edits an unrelated field on the same form
  and saves without retyping.
- Checking **Clear** with an empty input clears the stored value
  (column becomes ``NULL``).
- If a typed value and the **Clear** checkbox are submitted together,
  the typed value wins and the checkbox is ignored — the more
  conservative choice, since "don't lose what the user just typed" is
  safer than the alternative.

The eye-icon button toggles the visibility of what the user has
typed in the field — useful for verifying a freshly entered value
before clicking Update. The stored value is never revealed by this
toggle (or by anything else in the form), because the stored value
is never rendered into the form's HTML to begin with.

To bridge the resulting information gap (the form input is masked
whether or not a value is stored), the input's placeholder is
state-aware: it reads ``Stored (hidden) — type to replace`` when a
value is stored, and ``(not set) — type to add`` when nothing is
stored. A hover tooltip on the control reinforces the same idea.
The actual stored value is not communicated through either channel;
to view it, follow the read-only display pattern above.

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
