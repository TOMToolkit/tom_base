Encrypted Model Fields
======================

If your ``custom_code`` or reusable app contains a Model field storing user-specific
sensitive data, then you may want to encrypt that data.

Examples of user-specific sensitive
data include a password or API key for an external service that your TOM uses.
For example, TOMToolkit Facility modules can use the mechanism described here to store,
encrypted, user-specific credentials in a user profile model. Examples include the
`tom_eso <https://github.com/TOMToolkit/tom_eso>`__ and the
`tom_swift <https://github.com/TOMToolkit/tom_swift>`__ facility modules.

As we explain below, TOMToolkit provides a *mix-in* class, a *property descriptor*, and
utility functions to help encrypt user-specific sensitive data and access it when it's needed.

.. note:: For sensitive data that is used by the TOM itself and is not user-specific,
    we suggest that this data be stored outside the TOM and accessed through
    environment variables.

Creating and accessing an encrypted Model field
-----------------------------------------------

Creating an encrypted Model field
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your Model has a field that should be encrypted, follow these steps:

1. Import the mix-in class and property descriptor in your ``models.py``:

.. code-block:: python

    from tom_common.models import EncryptableModelMixin, EncryptedProperty

2. Make your Model subclass a subclass of ``EcryptableModelMixin``. For example:

.. code-block:: python

    class MyAppModel(EncryptableModelMixin, models.Model):
        ...

This gives your model access to a set of methods that will manage the encryption and
decryption of your data into and out of the ``BinaryField`` that stores the encrypted data.

3. Add the ``BinaryField`` that will store the encrypted data and the property descriptor
through which the ``BinaryField`` will be accessed.

.. code-block:: python

    _ciphertext_api_key = BinaryField(null=True, blank=True)  # encrypted data field (private)
    api_key = EncryptedProperty('_ciphertext_api_key')  # descriptor that provides access (public)

By convention name of the ``BinaryField`` field should begin with and underscore
(``_ciphertext_api_key`` in our example) because is it private to the Model class.

Accessing encrypted data
~~~~~~~~~~~~~~~~~~~~~~~~
The following example shows how to get and set an encrypted field using the utility
methods provided in ``tom_common.session_utils.py``:

.. code-block:: python

    from tom_common.session_utils import get_encrypted_field, set_encrypted_field
    from tom_app_example.models import MyAppModel
    
    profile: MyAppModel = user.myappmodel  # Model instance containing an encrypted field
    
    # getter example
    decrypted_api_key: str = get_encrypted_field(user, profile, 'api_key')
    
    # setter example
    new_api_key: str = 'something_secret'
    set_encrypted_field(user, profile, 'api_key', new_api_key)

Note here that the User instance (``user``) is used to access the ``EncryptableModelMixin``
subclass and its encrypted data. The ``user`` property of the Model subclass containing the
encrypted field (``MyAppModel`` in our example) is provided by the ``EncryptableModelMixin``.
As such, the model *should not define a* ``user`` *property of its own*.

Some Explanations
-----------------

EncryptableModelMixin (`source <https://github.com/TOMToolkit/tom_base/blob/069024f954e5540c1441c5186378de538f7d606f/tom_common/models.py#L100>`__)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The User's data is encrypted using (among other things) their password (i.e the
password they use to login to your TOM). When the User changes their password,
their encrypted data re-encrypted accordingly. The ``EncryptableModelMixin`` adds
method for this to your otherwise normal Django model.

EncryptedProperty (`source <https://github.com/TOMToolkit/tom_base/blob/069024f954e5540c1441c5186378de538f7d606f/tom_common/models.py#L39>`__)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A *property descriptor* implements the Python descriptor protocol (``__get__``,
``__set__``, etc). The ``EncryptedProperty`` property descriptor handles the details
of decrypting the encrypted ``BinaryField`` on its way out of the database and
encrypting it on the way in. It is invoked when the property is accessed
(e.g. ``model_instance.api_key``).

Session Utils (`example <https://github.com/TOMToolkit/tom_eso/blob/b74fe3b951ead6f6f332594724731d036944da47/tom_eso/eso.py#L209>`__)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``get_encrypted_field`` and ``set_encrypted_field`` functions implement
boilerplate code for creating and destroying the cipher used to encrypt and
decrypt the ``BinaryField``. *These methods must always be used to access any
encrypted field*.


The rest of the details are in the source code. If reading source code isn't your thing,
please do feel free to get in touch and we'll be happy to answer any questions you may have.
