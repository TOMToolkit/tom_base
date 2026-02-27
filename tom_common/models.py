import logging
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


class Profile(models.Model):
    """Profile model for a TOMToolkit User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'


class UserSession(models.Model):
    """Mapping model to associate the User and their Sessions

    An instance of this model is created whenever we receive the user_logged_in
    signal (see signals.py). Upon receiving user_logged_out, we delete all instances
    of UserSession for the specific User logging out.

    This allows us to manage the User's encrypted data in their app profiles,
    should they change their password (see signals.py).
    """
    # if either of the referenced objects are deleted, delete this object (CASCADE).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)

    def __str__(self):
        return f'UserSession for {self.user.username} with Session key {self.session.session_key}'


class EncryptedProperty:
    """
    A Python descriptor that provides transparent encryption and decryption for a
    model field.

    This descriptor is used in conjunction with the EncryptableModelMixin. It
    requires a cipher to be temporarily attached to the model instance as `_cipher`
    before accessing the property.

    Usage:
        class MyModel(EncryptableModelMixin, models.Model):
            _my_secret_encrypted = models.BinaryField(null=True)
            my_secret = EncryptedProperty('_my_secret_encrypted')
    """
    def __init__(self, db_field_name: str):
        self.db_field_name = db_field_name
        self.property_name = None  # Set by __set_name__

    def __set_name__(self, owner, name):
        self.property_name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self

        cipher = getattr(instance, '_cipher', None)
        if not isinstance(cipher, Fernet):
            raise AttributeError(
                f"A Fernet cipher must be set on the '{owner.__name__}' instance "
                f"as '_cipher' to access property '{self.property_name}'. "
                f"Please use session_utils.get_encrypted_field() instead of direct access."
            )

        encrypted_value = getattr(instance, self.db_field_name)
        if not encrypted_value:
            return ''

        # Handle bytes (sqlite3) vs memoryview (postgresql)
        if isinstance(encrypted_value, memoryview):
            # postgresql/psycopg uses a memoryview object for BinaryFields.
            # Sqlite3 uses bytes. When needed, convert to the encrypted_value
            # to bytes before we decrypt and decode it.
            encrypted_value = encrypted_value.tobytes()

        return cipher.decrypt(encrypted_value).decode()

    def __set__(self, instance, value: str):
        cipher = getattr(instance, '_cipher', None)
        if not isinstance(cipher, Fernet):
            raise AttributeError(
                f"A Fernet cipher must be set on the '{instance.__class__.__name__}' instance "
                f"as '_cipher' to set property '{self.property_name}'."
            )

        if not value:
            encrypted_value = None
        else:
            encrypted_value = cipher.encrypt(str(value).encode())

        setattr(instance, self.db_field_name, encrypted_value)


class EncryptableModelMixin(models.Model):
    """
    A mixin for models that use EncryptedProperty to handle sensitive data.

    Provides a generic re-encryption mechanism for all encrypted properties
    in the model.
    """
    # By defining the user relationship here, we ensure that any model using this
    # mixin has a standardized way to associate with a user. This removes
    # ambiguity and the need for assumptions in utility functions that need to
    # find the user associated with an encryptable model instance.
    # Subclasses should not redefine this field.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def reencrypt_model_fields(self, decoding_cipher: Fernet, encoding_cipher: Fernet) -> None:
        """Re-encrypts all fields managed by an EncryptedProperty descriptor.

        Re-encryption means decypting to plaintext with the old cipher based on the old
        password and re-encrypting the plaintext with the new cipher based on the new
        password.

        The `EncryptableModelMixin` and the `EncyptedProperty` descriptor work together
        to access the `Model`'s encytped `BinaryField`s (for setting, getting, and
        re-encrypting, which involves both).

        The `EncryptedProperty` descriptor uses the `_cipher` attribute on the encyrpted
        `BinaryField`-containing `Model` and this method sets and resets `_cipher` in the
        process of re-encrypting: First, `Model._cipher` is the `decoding_cipher` to get the
        plaintext value from the encrypted `BinaryField`. Second, `Model._cipher` is reset
        to the `encoding_cipher` to encrypt the plaintext value and save it in the
        `BinaryField`. Third, the `_cipher` attribute is removed from the `Model` until
        the next time it's needed, when it's attached again.

        So, to re-encrpyt, for each of the Model's encrypted `BinaryField`s, we need to:
          1. Use the `decoding_cipher` to get the `plaintext` of the value stored in the
             BinaryField. `self._cipher` is set to the `decoding_cipher` for this purpose
             and the `EncyptedProperty` descriptor handles the getting.
          2. Reset `self._cipher` to be the `encoding_cipher` and have the `EncyptedProperty`
             descriptor handle the encryption and setting.
          3. Remove the `_cipher` attribute from the Model.
        """
        model_save_needed = False
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            if isinstance(attr, EncryptedProperty):
                try:
                    # Set decoding cipher and get plaintext
                    self._cipher = decoding_cipher
                    plaintext = getattr(self, attr_name)

                    if plaintext:
                        # Set encoding cipher and set new value
                        self._cipher = encoding_cipher
                        setattr(self, attr_name, plaintext)
                        model_save_needed = True
                except Exception as e:
                    logger.error(f"Error re-encrypting property {attr_name} for {self.__class__.__name__}"
                                 f" instance {getattr(self, 'pk', 'UnknownPK')}: {e}")
                finally:
                    # Clean up the temporary cipher
                    if hasattr(self, '_cipher'):
                        del self._cipher
        if model_save_needed:
            self.save()

    def clear_encrypted_fields(self) -> None:
        """
        Clears all fields managed by an EncryptedProperty descriptor.

        This is a destructive operation used when re-encryption is not possible,
        e.g., when a user's password is reset by an admin and the old
        decryption key is unavailable. It sets the value of each encrypted
        field to None.
        """
        model_save_needed = False
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            if isinstance(attr, EncryptedProperty):
                # Directly set the underlying db field to None
                setattr(self, attr.db_field_name, None)
                model_save_needed = True
                logger.info(f"Cleared encrypted property '{attr_name}' for {self.__class__.__name__} "
                            f"instance {getattr(self, 'pk', 'UnknownPK')}.")
        if model_save_needed:
            self.save()

    class Meta:
        abstract = True
