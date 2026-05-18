Encryption and the SECRET_KEY
=====================================

This section is for TOM administrators and describes the relationship
between the ``settings.SECRET_KEY`` and the way TOMToolkit encrypts
sensitive user data. If you are a TOM developer looking for how to
create an encrypted database field, your documentation is here:
:doc:`/customization/encrypted_model_fields`

------

TOM Toolkit encrypts sensitive user data (API keys, observatory
credentials, anything declared with :class:`EncryptedProperty`) using a
single Fernet cipher derived from Django's ``settings.SECRET_KEY``.
That means when an encrypted field is written to or read from the database,
a cipher is created. The cipher can encrypt unencrypted plaintext (in) and decrypt
encrypted ciphertext (out). Cipher creation requires an encryption key.
TOMToolkit creates an encryption key that is based upon, but not identical
to, Django's ``settings.SECRET_KEY``. That's how the ``SECRET_KEY`` is related
to TOMToolkit's encryption. 

Treat ``SECRET_KEY`` like an encryption key
-------------------------------------------

If you lose ``SECRET_KEY`` (and any active
``SECRET_KEY_FALLBACKS`` entries), every encrypted field becomes
unrecoverable. Keep ``SECRET_KEY`` secret, never commit it, and back
it up through whatever channel your other production secrets use.

The standard Django guidance applies — see the
`Django deployment checklist
<https://docs.djangoproject.com/en/stable/howto/deployment/checklist/>`_
and the
`SECRET_KEY documentation
<https://docs.djangoproject.com/en/stable/ref/settings/#secret-key>`_.

.. warning::

   Rotating ``SECRET_KEY`` without first running the rotation procedure
   below will leave every previously-encrypted field unreadable. Follow
   the procedure exactly — don't just edit ``SECRET_KEY`` in your env.

   Should 

Graceful ``SECRET_KEY`` rotation
--------------------------------

Because TOMToolkit's encryption scheme depends on the value of ``settings.SECRET_KEY``,
if you need to change your ``SECRET_KEY``, we must decrypt the encrypted data
with a cipher derived from the old ``SECRET_KEY`` and re-encrypt it with a cipher derived
from the new ``SECRET_KEY``. The following proceed explains the process in full.

We use Django's built-in
`SECRET_KEY_FALLBACKS <https://docs.djangoproject.com/en/stable/ref/settings/#secret-key-fallbacks>`_
mechanism to rotate keys without an outage and without data loss. The
encryption module's ``decrypt()`` tries the primary derived key first
and then a derived key for each ``SECRET_KEY_FALLBACKS`` entry; the
``encrypt()`` path always uses the primary. So once a new
``SECRET_KEY`` is in place with the old key in fallbacks, *reads of
existing encrypted data continue to work*, and *new writes use the new
key*.

Scaffolded TOMs already include ``SECRET_KEY_FALLBACKS = []`` in their
``settings.py`` (added by ``tom_setup``); if your TOM predates that
template change, just add the line yourself.

The end-to-end procedure:

1. **Stage the old key as a fallback** and install a new
   ``SECRET_KEY``. In ``settings.py``, move the existing
   ``SECRET_KEY`` value into ``SECRET_KEY_FALLBACKS`` and set
   ``SECRET_KEY`` to the new value::

       SECRET_KEY = '<new key>'
       SECRET_KEY_FALLBACKS = ['<previously-current key>']

   (Or via env vars, whatever pattern your deployment uses.)

2. **Restart the server.** All existing encrypted data is still
   readable (via the fallback). All new writes — including any
   re-encryption — use the new primary key. Django's HMAC signing
   machinery also honours the fallback, so existing signed cookies
   and password-reset tokens stay valid.

3. **Re-encrypt existing data forward** so it no longer depends on the
   fallback::

       python manage.py rotate_encryption_key

   The command walks every :class:`EncryptedProperty` field across
   ``INSTALLED_APPS``, decrypts each value (transparently using either
   the primary or a fallback), and re-encrypts under the primary. After
   this, no value in the database requires the fallback to decrypt.

4. **Remove the fallback** from ``settings.py``::

       SECRET_KEY = '<new key>'
       SECRET_KEY_FALLBACKS = []

   Restart. You're now fully on the new key.

If anything goes wrong between steps 1 and 3, simply leave the fallback
in place — the system stays functional indefinitely with both keys
active. ``rotate_encryption_key`` is idempotent: running it again is
always safe.

If the command reports per-row failures, those rows were encrypted under
a key that is no longer in ``SECRET_KEY`` ∪ ``SECRET_KEY_FALLBACKS``
(i.e., that key has been forgotten). Add it back if you can; otherwise
the data on those rows is lost.

What if ``SECRET_KEY`` is lost?
-------------------------------

If you lose ``SECRET_KEY`` and have no backup:

- Every :class:`EncryptedProperty` value (saved API keys, observatory
  credentials) becomes unrecoverable. The ciphertext is still in the
  database; the key needed to decrypt it is gone.
- All Django signing-dependent state also breaks: outstanding password-
  reset tokens, signed URLs, persistent session cookies. Users will
  need to log in again and possibly re-enter any saved secrets.

Treat ``SECRET_KEY`` backup with the same seriousness as your database
backup.

Key Derivation Function Implementation Details
----------------------------------------------
The derivation uses `HKDF <https://en.wikipedia.org/wiki/HKDF>`_
(RFC 5869) with a domain-separator label, so the encryption key is
cryptographically independent of the way Django
uses ``SECRET_KEY`` for HMAC signing. See
:mod:`tom_common.encryption` for the implementation.


See also
--------

- :doc:`/customization/encrypted_model_fields` — how plugin authors
  declare and use encrypted fields.
- `Django deployment checklist
  <https://docs.djangoproject.com/en/stable/howto/deployment/checklist/>`_
  — the broader hardening you should do before going live.
