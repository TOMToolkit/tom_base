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


class EncryptedBinaryField(models.BinaryField):
    """A BinaryField that encrypts and decrypts its value using a Fernet cipher.

    This field is designed to securely store sensitive information by encrypting it before saving to the database
    and decrypting it when accessed.
    """
    def __init__(self, *args, **kwargs):
        """Wrap the BinaryField class to extend the constructor and the two new properties:

            :param encrypted: A boolean indicating whether the field should be encrypted.
            :param property_name: The name of the property (setter and getter) that will be used to set and get
            the encrypted value.

        The new properties are used by tom_common/session_utils.py to update each INSTALLED_APP's encrypted fields
        when the User changes their password.
        """
        # pop the encrypted and property_name from kwargs before calling super()
        self.encrypted: bool = kwargs.pop('encrypted', False)
        self.property_name: str = kwargs.pop('property_name', None)
        super().__init__(*args, **kwargs)


class EncryptableModelMixin(models.Model):
    """
    A mixin for models that contain EncryptedBinaryFields.
    Provides helper methods for encryption/decryption and a generic
    re-encryption mechanism for all encrypted fields in the model.

    TOMToolkit apps with encrypted models should define `get_<property_name>`
    and `set_<property_name>` methods for each EncryptedBinaryField,
    using the `_generic_decrypt` and `_generic_encrypt` helpers provided by this mixin.
    """

    def _generic_decrypt(self, encrypted_value, cipher: Fernet) -> str:
        """Generic decryption handling bytes vs memoryview."""
        if not encrypted_value:
            return ''
        if isinstance(encrypted_value, bytes):
            return cipher.decrypt(encrypted_value).decode()  # probably sqlite3 backend db
        else:  # Assumes memoryview or similar that has tobytes()
            return cipher.decrypt(encrypted_value.tobytes()).decode()  # probably postgresql backend db

    def _generic_encrypt(self, plaintext_value: str, cipher: Fernet) -> bytes:
        """Use the given to encrypt the plaintext, returning the encrypted bytes."""
        return cipher.encrypt(plaintext_value.encode())

    def reencrypt_model_fields(self, decoding_cipher: Fernet, encoding_cipher: Fernet) -> None:
        """Re-encrypts all fields in this model marked with 'encrypted=True'.

        Relies on the model having get_<property_name> and set_<property_name> methods
        for each field where `property_name` is defined on the EncryptedBinaryField.
        """
        model_save_needed = False
        for field in self._meta.fields:
            if getattr(field, 'encrypted', False):
                # make sure the field has a 'property_name' attribute
                if not hasattr(field, 'property_name') or not field.property_name:
                    logger.error(f"Field '{field.name}' in {self.__class__.__name__} is marked as "
                                 f" 'encrypted' but lacks 'property_name' for getter and setter. Skipping.")
                    continue

                # construct the setter/getter method names from the 'property_name' field attribute
                getter_name = f'get_{field.property_name}'
                setter_name = f'set_{field.property_name}'

                # make sure the model (self) has methods for the constructed method names
                if not hasattr(self, getter_name) or not hasattr(self, setter_name):
                    logger.error(f"Getter '{getter_name}' or setter '{setter_name}' not found for encrypted field "
                                 f"'{field.property_name}' in {self.__class__.__name__}. Skipping re-encryption.")
                    continue
                try:
                    field_getter = getattr(self, getter_name)
                    plaintext = field_getter(decoding_cipher)  # decryption finally happens here

                    field_setter = getattr(self, setter_name)
                    field_setter(plaintext, cipher=encoding_cipher)  # re-encryption finally happens here
                    model_save_needed = True
                except Exception as e:
                    logger.error(f"Error re-encrypting field {field.property_name} for {self.__class__.__name__}"
                                 f" instance {getattr(self, 'pk', 'UnknownPK')}: {e}")
        if model_save_needed:
            self.save()

    def clear_encrypted_fields(self) -> None:
        """
        Clears all fields in this model marked with 'encrypted=True'.

        This is a destructive operation used when re-encryption is not possible,
        e.g., when a user's password is reset by an admin and the old
        decryption key is unavailable. It sets the value of each encrypted
        field to None.
        """
        model_save_needed = False
        for field in self._meta.fields:
            if getattr(field, 'encrypted', False):
                # Directly set the field's value to None.
                # This bypasses the getter/setter logic which requires a cipher.
                setattr(self, field.attname, None)
                model_save_needed = True
                logger.info(f"Cleared encrypted field '{field.name}' for {self.__class__.__name__} "
                            f"instance {getattr(self, 'pk', 'UnknownPK')}.")
        if model_save_needed:
            self.save()

    class Meta:
        abstract = True
