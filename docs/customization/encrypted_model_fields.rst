Encrypted Model Fields
======================

If your ``custom_code`` or reusable app contains a model field storing
user-specific sensitive data, you may want to encrypt that data at rest.

Examples of user-specific sensitive data include passwords or API keys
for external services that your TOM uses on the user's behalf. TOM
Toolkit's Facility modules, for example, use the mechanism described
here to store user-specific external-service credentials in a user
profile model. Real examples live in
`tom_eso <https://github.com/TOMToolkit/tom_eso>`__ and
`tom_swift <https://github.com/TOMToolkit/tom_swift>`__.

How encryption works
--------------------

Encrypted fields are protected by a single Fernet cipher derived from
``settings.SECRET_KEY`` using HKDF (RFC 5869) with a domain-separator
label. There is no per-user key material and no additional environment
variable to manage. For the operator-side concerns (rotating
``SECRET_KEY`` without losing data, etc.) see
:doc:`/deployment/encryption`.

.. note::

   Encryption protects data from passive database exposure. It does NOT
   protect against a server administrator with access to ``SECRET_KEY``
   — by design, since the same admin needs to be able to run the
   ``rotate_encryption_key`` command. If you need user-level isolation
   from administrators, the toolkit's current scheme is not sufficient.

Adding an encrypted field to a model
------------------------------------

Two pieces are needed on the model: a ``BinaryField`` for the
ciphertext, and an :class:`EncryptedProperty` descriptor that handles
encryption on write and decryption on read.

.. code-block:: python

    from django.conf import settings
    from django.db import models
    from tom_common.models import EncryptedProperty


    class MyAppProfile(models.Model):
        user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE)
        _api_key_encrypted = models.BinaryField(null=True, blank=True)  # ciphertext (private)
        api_key = EncryptedProperty('_api_key_encrypted')               # descriptor (public)

By convention, the ``BinaryField``'s name starts with an underscore —
its only consumer is the :class:`EncryptedProperty` descriptor; plugin
code should never read or write it directly.

Reading and writing the field
-----------------------------

Plain Python attribute access on the descriptor handles everything:

.. code-block:: python

    profile.api_key = 'something-secret'
    profile.save()

    # later, possibly in a different process / request:
    value = profile.api_key   # 'something-secret'

On assignment, the descriptor calls
:func:`tom_common.encryption.encrypt`, which builds a Fernet cipher
from ``settings.SECRET_KEY`` and encrypts the value, then stores the
ciphertext bytes in the underlying ``BinaryField``. On read, the
descriptor calls :func:`tom_common.encryption.decrypt`, which
transparently honours ``settings.SECRET_KEY_FALLBACKS`` (see
:doc:`/deployment/encryption` for the rotation procedure).

An empty string assignment clears the ciphertext (stores ``None`` in
the ``BinaryField``). Reading an unset / empty field yields ``''``,
not ``None`` — so consumers don't need to special-case the empty case.

Some explanations
-----------------

:class:`EncryptedProperty` (`source <https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/models.py>`__)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A *property descriptor* implementing the Python descriptor protocol
(``__get__``, ``__set__``, ``__set_name__``). It handles the details of
decrypting the ciphertext ``BinaryField`` on its way out of the
database and encrypting it on the way in. It is invoked whenever the
property is accessed (e.g. ``profile.api_key`` reads;
``profile.api_key = 'x'`` writes).

The descriptor reads the cipher from
:func:`tom_common.encryption._get_cipher` on every access, so changes
to ``settings.SECRET_KEY`` (via ``override_settings`` in tests, or a
deployment-level rotation) take effect immediately on the next read.

The rest of the details are in the source. If reading source isn't
your thing, feel free to get in touch and we'll be happy to answer
questions.
