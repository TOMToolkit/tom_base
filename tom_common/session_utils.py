import base64
import logging
import inspect

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from django.apps import apps
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore

from tom_common.models import UserSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constant for storing the cipher encryption key in the session
SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY = 'key'


def create_cipher_encryption_key(user, password: str) -> bytes:
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

    # Save key in Session (encryption_key must be encoded as a string to store in Session)
    b64encoded_key_as_str: str = base64.b64encode(key).decode('utf-8')  # encode key as str
    session_store[SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY] = b64encoded_key_as_str  # save key in Session
    session_store.save()  # we might be accessing the session before it's saved (in the middleware?)


def extract_key_from_session(session: Session) -> bytes:
    """Extracts and decodes the encryption key from a Django Session object.

    Retrieves the base64 encoded key string from the session, decodes it
    from base64, and returns the raw bytes of the encryption key.

    Args:
        session: The Django Session object from which to extract the key.

    Returns:
        The encryption key as bytes.
    """
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} **********")
    logger.debug(f"Extracting key from Session: {type(session)} = {session} - {session.get_decoded()}")
    b64encoded_key: str = session.get_decoded()[SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY]  # get the key from the session
    recovered_key: bytes = base64.b64decode(b64encoded_key.encode('utf-8'))  # decode key to bytes from str
    return recovered_key


def extract_key_from_session_store(session_store: SessionStore) -> bytes:
    """Extracts the encryption key from a Django SessionStore instance.

    This function first retrieves the underlying Session object using the
    session_key from the SessionStore. It then calls
    `extract_key_from_session` to get the actual key.

    Args:
        session_store: The Django SessionStore instance.

    Returns:
        The encryption key as bytes.
    """
    try:
        assert isinstance(session_store, SessionStore), \
            f"session_store is not a SessionStore; it's a {type(session_store)}"
    except AssertionError as e:
        logger.error(str(e))

        # the session_store is not a SessionStore, but a Session instance
        # does the session instance have the same session_key attribute as the SessionStore?
        # log the attributes of the session_store
        logger.debug(f"Session attributes: {vars(session_store)}")  # log the attributes of the session_store

        session: Session = Session.objects.get(pk=session_store.session_key)

        assert session == session_store

    session: Session = Session.objects.get(pk=session_store.session_key)
    return extract_key_from_session(session)


def reencrypt_sensitive_data(user) -> None:
    """Re-encrypts sensitive data for a user after a password change.

    This function is typically called when a user changes their password. It performs
    the following steps:
    1. Retrieves the current encryption key from the user's session.
    2. Creates a new encryption key based on the user's new password.
    3. Iterates through all installed Django apps, calling a `reencrypt_app_fields`
       method on each app's config (if it exists). This method is responsible for
       decrypting data with the old key and re-encrypting it with the new key.
    4. Saves the new encryption key to the user's session.

    Args:
        user: The Django User object whose sensitive data needs re-encryption.
    """
    logger.debug("Re-encrypting sensitive data...")

    #  Get the current Session from the UserSession
    try:
        session: Session = UserSession.objects.get(user=user).session
    except UserSession.DoesNotExist:
        logger.error(f"User {user.username} does not have a UserSession. Cannot re-encrypt sensitive data.")
        return

    #  Get the current encryption_key from the Session
    current_encrytption_key: bytes = extract_key_from_session(session)
    #  Generate a decoding Fernet cipher with the current encryption key
    decoding_cipher = Fernet(current_encrytption_key)

    #  Get the new raw password from the User instance
    new_raw_password = user._password  # CAUTION: this is implemenation dependent (using _<property>)
    #  Generate a new encryption_key with the new raw password
    new_encryption_key: bytes = create_cipher_encryption_key(user, new_raw_password)
    #  Generate a new encoding Fernet cipher with the new encryption key
    encoding_cipher = Fernet(new_encryption_key)

    # test both those ciphers to see if they work
    test_plaintext = 'this is a test'
    # first test the decoding cipher
    ciphertext_d = decoding_cipher.encrypt(test_plaintext.encode())
    decoded_ciphertext = decoding_cipher.decrypt(ciphertext_d).decode()
    logger.debug(f'**** decoding_cypher: {test_plaintext} -> {decoded_ciphertext}')
    # now test the encoding cipher
    ciphertext_e = encoding_cipher.encrypt(test_plaintext.encode())
    decoded_ciphertext = encoding_cipher.decrypt(ciphertext_e).decode()
    logger.debug(f'**** encoding_cypher: {test_plaintext} -> {decoded_ciphertext}')
    # show that the ciphertext is different
    logger.debug(f'**** ciphertext_d: {type(ciphertext_d)} = {ciphertext_d}')
    logger.debug(f'**** ciphertext_e: {type(ciphertext_e)} = {ciphertext_e}')
    assert ciphertext_d != ciphertext_e, "Ciphertext should be different for different keys"

    #  Save the new encryption key in the User's Session
    session_store: SessionStore = SessionStore(session_key=session.session_key)
    save_key_to_session_store(new_encryption_key, session_store)

    # Loop through all the installed apps and ask them to reencrypt their encrypted profile fields
    for app_config in apps.get_app_configs():
        try:
            app_config.reencrypt_app_fields(user, decoding_cipher, encoding_cipher)
        except AttributeError:
            logger.debug(f'App: {app_config.name} does not have a reencrypt_app_fields method.')
            continue