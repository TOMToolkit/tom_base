import base64
import logging
from typing import Optional, TypeVar

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from django.apps import AppConfig, apps
from django.db import models
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore

from tom_common.models import EncryptableModelMixin, UserSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constant for storing the cipher encryption key in the session
SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY = 'key'

# A generic TypeVar for a Django models.Model subclass instance.
# The `bound=models.Model` constraint ensures that any
# type used for ModelType must be a subclass of `models.Model`.
ModelType = TypeVar('ModelType', bound=models.Model)


def create_cipher_encryption_key(user: User, password: str) -> bytes:
    """Creates a Fernet cipher encryption key derived from the user's password.

    This key is intended to be stored (e.g., in the session) and used to
    instantiate Fernet ciphers for encrypting and decrypting sensitive data
    associated with the user, such as API keys or external service credentials.

    The key derivation process uses PBKDF2HMAC with a salt generated from
    the user's username, making the key unique per user and password.

    Args:
        user: The Django User object.
        password: The user's plaintext password.

    Returns:
        A URL-safe base64-encoded Fernet encryption key as bytes.

    See Also:
        https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
    """

    # Generate a salt from hash and username
    salt = hashes.Hash(hashes.SHA256(), backend=default_backend())
    salt.update(user.username.encode())

    # Derive encryption_key using PBKDF2-HMAC and the newly generated salt
    kdf = PBKDF2HMAC(  # key derivation function
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.finalize()[:16],  # only finalize once; returns bytes; use 16 bytes
        iterations=1_000_000,  # Django recommendation of jan-2025
        backend=default_backend(),
    )
    encryption_key: bytes = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return encryption_key


def save_key_to_session_store(key: bytes, session_store: SessionStore) -> None:
    """Saves the provided encryption key to the given Django session store.

    The key is first base64 encoded and converted to a string before being
    stored in the session under a predefined session key.

    Args:
        key: The encryption key (bytes) to be saved.
        session_store: The Django SessionStore instance where the key will be saved.
    """
    try:
        assert isinstance(session_store, SessionStore), \
            f"session_store is not a SessionStore; it's a {type(session_store)}"
    except AssertionError as e:
        logger.error(str(e))

    # The key is bytes, but session values must be JSON-serializable.
    # A Fernet key is already base64-encoded, so we just decode it to a string for storage.
    session_store[SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY] = key.decode('utf-8')
    session_store.save()  # we might be accessing the session before it's saved (in the middleware?)


def get_key_from_session_model(session: Session) -> bytes:
    """Extracts and decodes the encryption key from a Django Session object.

    Retrieves the base64 encoded key string from the session, decodes it
    from base64, and returns the raw bytes of the encryption key.

    Args:
        session: The Django Session object from which to extract the key.

    Returns:
        The encryption key as bytes.
    """

    logger.debug(f"Extracting key from Session model: {type(session)} = {session} - {session.get_decoded()}")
    key_as_str: str = session.get_decoded()[SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY]  # type: ignore
    # The key was stored as a string, so we encode it back to bytes.
    return key_as_str.encode('utf-8')


def get_key_from_session_store(session_store: SessionStore) -> bytes:
    """Extracts the encryption key from a Django SessionStore instance.

    Use the dictionary-like API that the SessionStore provides to retreive
    the encryption key.

    Args:
        session_store: The Django SessionStore instance.

    Returns:
        The encryption key as bytes.
    """
    if not isinstance(session_store, SessionStore):
        # manual type checking
        raise TypeError(f"Expected a SessionStore object, but got {type(session_store)}")

    key_as_str: str = session_store[SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY]
    return key_as_str.encode('utf-8')


def get_encrypted_field(user: User,
                        model_instance: ModelType,  # type: ignore
                        field_name: str) -> Optional[str]:
    """
    Helper function to safely get the decrypted value of an EncryptedProperty.

    This function encapsulates the logic of fetching the user's session key,
    creating a cipher, attaching it to the model instance, reading the
    decrypted value, and cleaning up.

    Args:
        user: The User object associated with the encrypted data.
        model_instance: The model instance containing the EncryptedProperty.
        field_name: The string name of the EncryptedProperty to access.

    Returns:
        The decrypted string value, or None if decryption fails for any reason
        (e.g., no active session, key not found).
    """
    try:
        #  Get the current Session from the UserSession
        # A user can be logged in from multiple browsers, resulting in multiple
        # UserSession objects. Since the encryption key is derived from the
        # password and is the same for all sessions, we can safely take the first one.
        user_session = UserSession.objects.filter(user=user).first()
        if not user_session:
            raise UserSession.DoesNotExist(f"No active session found for user {user.username}")

        session: Session = user_session.session
        cipher_key: bytes = get_key_from_session_model(session)
        cipher: Fernet = Fernet(cipher_key)

        # Attach the cipher, get the value, and then clean up
        model_instance._cipher = cipher  # type: ignore
        decrypted_value = getattr(model_instance, field_name)
        return decrypted_value
    except (UserSession.DoesNotExist, KeyError) as e:
        logger.warning(f"Could not get encryption key for user {user.username} to access "
                       f"'{field_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while decrypting field '{field_name}' "
                     f"for user {user.username}: {e}")
        return None
    finally:
        # Ensure the temporary cipher is always removed from the instance
        if hasattr(model_instance, '_cipher'):
            del model_instance._cipher  # type: ignore


def set_encrypted_field(user: User,
                        model_instance: ModelType,  # type: ignore
                        field_name: str,
                        value: str) -> bool:
    """
    Helper function to safely set the value of an EncryptedProperty.

    This function encapsulates the logic of fetching the user's session key,
    creating a cipher, attaching it to the model instance, setting the new
    encrypted value, and cleaning up.

    Note: This function does NOT save the instance. The caller is responsible
    for calling `instance.save()` after the field has been set.

    Args:
        user: The User object associated with the encrypted data.
        model_instance: The model instance containing the EncryptedProperty.
        field_name: The string name of the EncryptedProperty to set.
        value: The plaintext string value to encrypt and set.

    Returns:
        True if the field was set successfully, False otherwise.
    """
    try:
        #  Get the current Session from the UserSession
        user_session = UserSession.objects.filter(user=user).first()  # see comment above
        if not user_session:
            raise UserSession.DoesNotExist(f"No active session found for user {user.username}")

        session: Session = user_session.session
        cipher_key: bytes = get_key_from_session_model(session)
        cipher = Fernet(cipher_key)

        # Attach the cipher, set the value, and then clean up
        model_instance._cipher = cipher  # type: ignore
        setattr(model_instance, field_name, value)
        return True
    except (UserSession.DoesNotExist, KeyError) as e:
        logger.error(f"Could not get encryption key for user {user.username} to set "
                     f"'{field_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while encrypting field '{field_name}' "
                     f"for user {user.username}: {e}")
        return False
    finally:
        # Ensure the temporary cipher is always removed from the instance
        if hasattr(model_instance, '_cipher'):
            del model_instance._cipher  # type: ignore


def reencrypt_data(user) -> None:
    """Re-encrypts sensitive data for a user after a password change.

    If an Administrator is changing another user's password, and
    the `user: User` is not logged-in, then they have no SessionStore,
    and, thus, no encryption key is available. In that case, the User's
    encrypted fields are cleared out because they are stale, having
    been ecrypted with an encryption key derived from a password that
    is no longer in use.

    Args:
        user: The Django User object whose password has changed.
    """
    logger.debug("Re-encrypting sensitive data...")

    #  Get the current Session from the UserSession
    user_session = UserSession.objects.filter(user=user).first()  # see comment above

    if not user_session:
        logger.warning(f"User {user.username} is not logged in. Cannot re-encrypt sensitive data. "
                       f"Clearing all encrypted fields instead.")
        # Loop through all the installed apps and ask them to clear their encrypted profile fields
        for app_config in apps.get_app_configs():
            clear_encrypted_fields_for_user(app_config, user)  # type: ignore
        return

    session: Session = user_session.session
    #  Get the current encryption_key from the Session
    current_encryption_key: bytes = get_key_from_session_model(session)
    #  Generate a decoding Fernet cipher with the current encryption key
    decoding_cipher = Fernet(current_encryption_key)

    #  Get the new raw password from the User instance
    new_raw_password = user._password  # CAUTION: this is implemenation dependent (using _<property>)
    #  Generate a new encryption_key with the new raw password
    new_encryption_key: bytes = create_cipher_encryption_key(user, new_raw_password)
    #  Generate a new encoding Fernet cipher with the new encryption key
    encoding_cipher = Fernet(new_encryption_key)

    #  Save the new encryption key in the User's Session
    session_store: SessionStore = SessionStore(session_key=session.session_key)
    save_key_to_session_store(new_encryption_key, session_store)
    # also, attach the new encryption key to the User instance so it can be inserted
    # into the Session before we call update_session_auth_hash in
    # tom_common.views.UserUpdateView.form_valid()
    user._temp_new_fernet_key = new_encryption_key

    # Loop through all the installed apps and ask them to reencrypt their encrypted profile fields
    for app_config in apps.get_app_configs():
        try:
            reencrypt_encypted_fields_for_user(app_config, user, decoding_cipher, encoding_cipher)  # type: ignore
        except AttributeError:
            logger.debug(f'App: {app_config.name} does not have a reencrypt_app_fields method.')
            continue


def reencrypt_encypted_fields_for_user(app_config: AppConfig, user: 'User',
                                       decoding_cipher: Fernet, encoding_cipher: Fernet):
    """
    Automatically finds models in the app_config that inherit from EncryptableModelMixin
    and attempts to re-encrypt their fields for the given user.

    :param app_config: The AppConfig instance of the plugin app.
    :param user: The User whose data needs re-encryption.
    :param decoding_cipher: Fernet cipher to decrypt existing data.
    :param encoding_cipher: Fernet cipher to encrypt new data.
    """
    for model_class in app_config.get_models():
        if issubclass(model_class, EncryptableModelMixin):
            logger.debug(f"Found EncryptableModelMixin subclass: {model_class.__name__} in app {app_config.name}")
            # The EncryptableModelMixin guarantees a 'user' field, which is a OneToOneField.
            try:
                encryptable_model_instance = model_class.objects.get(user=user)
                # instance of the Model which is a subclass of EncryptableModelMixin
                encryptable_model_instance.reencrypt_model_fields(decoding_cipher, encoding_cipher)  # re-entrpt here
            except model_class.DoesNotExist:
                logger.info(f"No {model_class.__name__} instance found for user {user.username}.")
            except model_class.MultipleObjectsReturned:
                # This should not be reached if the mixin correctly enforces a OneToOneField.
                # It's kept here as a safeguard against unexpected configurations.
                logger.error(f"Multiple {model_class.__name__} instances found for user {user.username}. "
                             f"This is unexpected for an EncryptableModelMixin. Re-encrypting all found.")
                instances = model_class.objects.filter(user=user)
                for encryptable_model_instance in instances:
                    encryptable_model_instance.reencrypt_model_fields(decoding_cipher, encoding_cipher)
            except Exception as e:
                logger.error(f"Error processing model {model_class.__name__} for re-encryption for "
                             f"user {user.username}: {e}")


def clear_encrypted_fields_for_user(app_config: AppConfig, user: 'User',) -> None:
    """
    Finds models in an app that are Encryptable and clears their encrypted fields for the given user.

    This is a destructive operation used when a user's password is reset without
    them being logged in, making the old decryption key unavailable. This happens,
    for example, when an adminitrator resets their password.

    :param app_config: The AppConfig instance of the plugin app.
    :param user: The User whose data needs to be cleared.
    """
    for model_class in app_config.get_models():
        if issubclass(model_class, EncryptableModelMixin):
            logger.debug(f"Found EncryptableModelMixin subclass: {model_class.__name__} in "
                         f"app {app_config.name} for clearing.")
            # The EncryptableModelMixin now guarantees a 'user' field, which is a OneToOneField.
            try:
                encryptable_model_instance = model_class.objects.get(user=user)
                # instance of the Model which is a subclass of EncryptableModelMixin
                encryptable_model_instance.clear_encrypted_fields()  # do the clearing of the fields here
            except model_class.DoesNotExist:
                logger.info(f"No {model_class.__name__} instance found for user {user.username} to clear.")
            except model_class.MultipleObjectsReturned:
                # This should not be reached if the mixin correctly enforces a OneToOneField.
                # It's kept here as a safeguard against unexpected configurations.
                logger.error(f"Multiple {model_class.__name__} instances found for user {user.username}. "
                             f"This is unexpected for an EncryptableModelMixin. Clearing all found.")
                instances = model_class.objects.filter(user=user)
                for encryptable_model_instance in instances:
                    encryptable_model_instance.clear_encrypted_fields()
            except Exception as e:
                logger.error(f"Error clearing encrypted fields for model {model_class.__name__} for "
                             f"user {user.username}: {e}")
