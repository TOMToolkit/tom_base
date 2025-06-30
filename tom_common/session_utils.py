import base64
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from django.apps import AppConfig, apps
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore

from tom_common.models import UserSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constant for storing the cipher encryption key in the session
SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY = 'key'


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
    try:
        session: Session = UserSession.objects.get(user=user).session
    except UserSession.DoesNotExist:
        logger.warning(f"User {user.username} is not logged in. Cannot re-encrypt sensitive data. "
                       f"Clearing all encrypted fields instead.")
        # Loop through all the installed apps and ask them to clear their encrypted profile fields
        for app_config in apps.get_app_configs():
            clear_encrypted_fields_for_user(app_config, user)  # type: ignore
        return

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


def reencrypt_encypted_fields_for_user(
    app_config: AppConfig,
    user: 'User',  # noqa # type: ignore
    decoding_cipher: Fernet,
    encoding_cipher: Fernet,
    user_relation_field_name: str = 'user'
):
    """
    Automatically finds models in the app_config that inherit from EncryptableModelMixin
    and attempts to re-encrypt their fields for the given user.

    :param app_config: The AppConfig instance of the plugin app.
    :param user: The User whose data needs re-encryption.
    :param decoding_cipher: Fernet cipher to decrypt existing data.
    :param encoding_cipher: Fernet cipher to encrypt new data.
    :param user_relation_field_name: The name of the field on the plugin's model
                                     that links to the Django User model.
    """
    # Import models here, when the function is called, ensuring apps are ready.
    from django.contrib.auth.models import User  # noqa
    from tom_common.models import EncryptableModelMixin

    for model_class in app_config.get_models():
        if issubclass(model_class, EncryptableModelMixin):
            logger.debug(f"Found EncryptableModelMixin subclass: {model_class.__name__} in app {app_config.name}")
            # the Model must have a ForeignKey to the User (and AppProfile Models do)
            if hasattr(model_class, user_relation_field_name):
                try:
                    # Handles OneToOneField or unique ForeignKey to User
                    instance = model_class.objects.get(**{user_relation_field_name: user})
                    # instance of the Model which is a subclass of EncryptableModelMixin
                    instance.reencrypt_model_fields(decoding_cipher, encoding_cipher)  # do the re-encryption here
                except model_class.DoesNotExist:
                    logger.info(f"No {model_class.__name__} instance found for user {user.username} "
                                f"via field '{user_relation_field_name}'.")
                except model_class.MultipleObjectsReturned:
                    # Handles non-unique ForeignKey to User
                    logger.warning(f"Multiple {model_class.__name__} instances found for user {user.username} via "
                                   f"field '{user_relation_field_name}'. Re-encrypting all.")
                    instances = model_class.objects.filter(**{user_relation_field_name: user})
                    for instance in instances:
                        instance.reencrypt_model_fields(decoding_cipher, encoding_cipher)
                except Exception as e:
                    logger.error(f"Error processing model {model_class.__name__} for re-encryption for "
                                 f"user {user.username}: {e}")
            else:
                logger.warning(f"Model {model_class.__name__} is Encryptable but does not have a direct "
                               f"'{user_relation_field_name}' attribute. Cannot automatically fetch instance "
                               f"for user {user.username} for re-encryption.")


def clear_encrypted_fields_for_user(
    app_config: AppConfig,
    user: 'User',
    user_relation_field_name: str = 'user'
):
    """
    Finds models in an app that are Encryptable and clears their encrypted fields for a given user.

    This is a destructive operation used when a user's password is reset without
    them being logged in, making the old decryption key unavailable.

    :param app_config: The AppConfig instance of the plugin app.
    :param user: The User whose data needs to be cleared.
    :param user_relation_field_name: The name of the field on the plugin's model
                                     that links to the Django User model.
    """
    from tom_common.models import EncryptableModelMixin

    for model_class in app_config.get_models():
        if issubclass(model_class, EncryptableModelMixin):
            logger.debug(f"Found EncryptableModelMixin subclass: {model_class.__name__} in "
                         f"app {app_config.name} for clearing.")
            if hasattr(model_class, user_relation_field_name):
                try:
                    # Handles OneToOneField or unique ForeignKey to User
                    instance = model_class.objects.get(**{user_relation_field_name: user})
                    # instance of the Model which is a subclass of EncryptableModelMixin
                    instance.clear_encrypted_fields()  # do the clearing of the fields here
                except model_class.DoesNotExist:
                    logger.info(f"No {model_class.__name__} instance found for user {user.username} "
                                f"via field '{user_relation_field_name}' to clear.")
                except model_class.MultipleObjectsReturned:
                    # Handles non-unique ForeignKey to User
                    logger.warning(f"Multiple {model_class.__name__} instances found for user {user.username} via "
                                   f"field '{user_relation_field_name}'. Clearing all.")
                    instances = model_class.objects.filter(**{user_relation_field_name: user})
                    for instance in instances:
                        instance.clear_encrypted_fields()
                except Exception as e:
                    logger.error(f"Error clearing encrypted fields for model {model_class.__name__} for "
                                 f"user {user.username}: {e}")
