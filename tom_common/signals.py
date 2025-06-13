import logging
import inspect

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from rest_framework.authtoken.models import Token

from tom_common.models import Profile, UserSession
from .session_utils import (
    create_cipher_encryption_key,
    save_key_to_session_store,
    extract_key_from_session_store,
    reencrypt_sensitive_data,
    SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# NOTE: there are two ways to reference the User model: settings.AUTH_USER_MODEL and get_user_model()
# see https://docs.djangoproject.com/en/stable/topics/auth/customizing/#referencing-the-user-model
# Basically, settings.AUTH_USER_MODEL is for code that is executed upon import,
# while get_user_model() is valid after INSTALLED_APPS are loaded.


# Signal: Create a Profile for the User when the User instance is created
@receiver(post_save, sender=User)
def save_profile_on_user_pre_save(sender, instance, **kwargs):
    """When a user is saved, save their profile."""
    # Take advantage of the fact that logging in updates a user's last_login field
    # to create a profile for users that don't have one.
    try:
        instance.profile.save()
    except User.profile.RelatedObjectDoesNotExist:
        logger.info(f'No Profile found for {instance}. Creating Profile.')
        Profile.objects.create(user=instance)


# Signal: Create a DRF token for the User when the User instance is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token_on_user_pre_save(sender, instance=None, created=False, **kwargs):
    """Create a token for the User when the User instance is created.

    This is the API token used by the User to authenticate with the
    Django REST framework API.

    For more information, see the Django REST framework documentation:
    https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication
    """
    if created:
        Token.objects.create(user=instance)


# Here, we're setting up a mechanism to encrypt sensitive User data like
# API keys and password for Facilities and data services, etc. The Signals
# above create and clear the pher upon login and logout, respevely.
# We use the user_logged_in signal to intercept the User's password and
# use that to derive the encryption_key and use that to create the cipher.

# Signal: Create UserSession on login
@receiver(user_logged_in)
def create_user_session_on_user_logged_in(sender, request, user, **kwargs) -> None:
    """Whenever a user logs in, create a UserSession instance to associate
    the User with the new Session.
    """
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} sender: {sender} **********")
    logger.debug(f"User {user.username} has logged in. request: {request}")
    logger.debug(f"Request session: {type(request.session)} = {request.session}")

    # the request.session is a SessionStore object, we need the Session
    # and we can get it using the session_key
    try:
        session: Session = Session.objects.get(pk=request.session.session_key)
    except Session.DoesNotExist:
        # this request should have a sesssion: SessionStore object, and if it
        # doesn't, it could be because the user was logged in as part of a test, but
        # TODO: sort out whether the test code should be updated or ???
        logger.error(f"Session {request.session.session_key} does not exist.")
        return

    logger.debug(f"Session: {type(session)} = {session}")

    user_session, created = UserSession.objects.get_or_create(user=user, session=session)
    if created:
        logger.debug(f"UserSession created: {user_session}")
    else:
        logger.debug(f"UserSession already exists: {user_session}")


# Signal: Delete UserSession on logout
@receiver(user_logged_out)
def delete_user_session_on_user_logged_out(sender, request, user, **kwargs) -> None:
    """Whenever a user logs out, delete all their UserSession instances.
    """
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} sender: {sender} **********")

    user_sessions = UserSession.objects.filter(user=user)
    for user_session in user_sessions:
        user_session.session.delete()
    # TODO: consider if the User has logged in from multiple browsers/devices
    # (i.e. we want to delete all their sessions or just the one they logged out from)
    # this could probably be done by filtering on the session_key of the request in
    # addition to the user above.


# Signal: Set cipher on login
@receiver(user_logged_in)
def set_cipher_on_user_logged_in(sender, request, user, **kwargs) -> None:
    """When the user logs in, capture their password and use it to
    generate a cipher encryption key and save it in the User's Session.
    """
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} sender: {sender} **********")
    logger.debug(f"User {user.username} has logged in. request: {request}")

    password = request.POST.get("password")  # Capture password from login
    logger.debug(f"Password: {password}")
    if password:
        logger.debug(f"Creating encryption key for user: {user.username} with password {password} ...")
        encryption_key: bytes = create_cipher_encryption_key(user, password)
        save_key_to_session_store(encryption_key, request.session)

        # TODO: remove this testing code
        # TESTING FOLLOWS: test key recovery and cipher
        # 1. encode plaintext with cipher created with original key
        cipher = Fernet(encryption_key)
        plaintext = 'This is a test message.'
        ciphertext = cipher.encrypt(plaintext.encode())
        cipher = None  # destroy cipher (not really necessary for this test)

        # 2. decode ciphertext with cipher created with recovered key
        recovered_key: bytes = extract_key_from_session_store(request.session)  # get the key from the session
        new_cipher = Fernet(recovered_key)  # create cipher from recovered key
        recovered_plaintext = new_cipher.decrypt(ciphertext).decode()

        logger.debug(f"Test: {plaintext} -> {recovered_plaintext} via {ciphertext}")
    else:
        logger.error(f'User {user.username} logged in without a password. Cannot create encryption key.')


# Signal: Clear cipher encryption key on logout
@receiver(user_logged_out)
def clear_encryption_key_on_user_logged_out(sender, request, user, **kwargs) -> None:
    """Clear the cipher encryption key when a user logs out.
    """
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} sender: {sender} **********")

    if user:
        logger.debug(f'User {user.username} has logged out. Deleting key from Session.'
                     f'sender: {sender}; request: {request}')
        request.session.pop(SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY, None)


def reencrypt_sensitive_data(user) -> None:
    """Re-encrypt the user's sensitive data with the new password."""
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} **********")
    logger.debug("Re-encrypting sensitive data...")

    #  Get the current Session from the UserSession
    try:
        session: Session = UserSession.objects.get(user=user).session
    except UserSession.DoesNotExist:
        logger.error(f"User {user.username} does not have a UserSession. Cannot re-encrypt sensitive data.")
        return

    #  Get the current encryption_key from the Session
    current_encryption_key: bytes = extract_key_from_session(session)
    #  Generate a decoding Fernet cipher with the current encryption key
    decoding_cipher = Fernet(current_encryption_key)

    #  Get the new raw password from the User instance
    new_raw_password = user._password  # CAUTION: this is implementation dependent (using _<property>)
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
    # TODO: clean up the SessionStore/Session APIs/function signitures - we're going in circles

    # Loop through all the installed apps and ask them to reencrypt their encrypted profile fields
    for app in apps.get_app_configs():
        try:
            app.reencrypt_app_fields(user, decoding_cipher, encoding_cipher)
        except AttributeError as e:
            logger.debug(f'App: {app.name}: {type(app)} does not have a reencrypt_profile_fields method. Error: {e}')
            if app.name == 'tom_eso':
                logger.debug(f'App: {app.name} directory: {dir(app)}')
                logger.debug(f'App: {app.name} encrypted fields  {app.encrypted_profile_fields()}')
                app.reencrypt_app_fields(user, decoding_cipher, encoding_cipher)  # TODO: remove this line it's just here to generate a stack trace
            continue


# Signal: Update the User's sensitive data when the password changes
@receiver(pre_save, sender=get_user_model())
def user_updated_on_user_pre_save(sender, **kwargs):
    """When the User model is saved, detect if the password has changed.

    kwargs:
     * signal: <django.db.models.signals.ModelSignal>
     * instance: <User>
     * raw: Boolean
     * using: str
     * update_fields: frozenset | NoneType

    If the User's password has changed, take the following actions:

    Current list of actions to be taken upon User password change:
     * re-encrypt the user's sensitive data (see reencrypt_sensitive_data() function)
     *
    """
    logger.debug(f"********** {inspect.currentframe().f_code.co_name} sender: {sender} **********")
    logger.debug(f"kwargs: {kwargs}")
    user = kwargs.get("instance", None)

    # logger.debug('here are the kwargs of the pre_save signal (filtered by sender=get_user_model()):')
    # for key, value in kwargs.items():
    #     logger.debug(f'    {key}: {value}: {type(value)}')
    # here are the kwargs of the pre_save signal (filtered by sender=get_user_model()):
    # signal: <django.db.models.signals.ModelSignal object at 0x7fb74963cd90>: <class 'django.db.models.signals.ModelSignal'>
    # instance: admin: <class 'django.contrib.auth.models.User'>
    # raw: False: <class 'bool'>
    # using: default: <class 'str'>
    # update_fields: None: <class 'NoneType'>

    if user and not user.username == 'AnonymousUser' and not user.is_anonymous:
        # TODO: It's bad design to have a User with username: AnonymousUser and is_anonymous=True !!!

        # user.password vs. user._password:
        # the user.password field is used for authentication (via comparison to the (hashed) password
        # being tested for validity). The _password field is the raw password and is what we need to
        # create a new cipher for the User's sensitive data.

        # This Signal is called for ANY change to the User model, not just password changes.
        # So, determine if the password has changed by comparing new and old (hashed) passwords.
        # NOTE: the update_fields kwarg is a frozenset of changed updated fields, but it does not contain
        # 'password' when the User is changing their password. So, compare new and old:

        new_hashed_password = user.password  # from the not-yet-saved User instance
        try:
            old_hashed_password = User.objects.get(id=user.id).password  # from the previously-saved User instance
        except User.DoesNotExist:
            old_hashed_password = None

        if new_hashed_password != old_hashed_password:
            # New password detected
            new_raw_password = user._password  # CAUTION: this is implemenation dependent (using _<property>)
            logger.debug(f'User {user.username} is changing their password to {new_raw_password}')
            reencrypt_sensitive_data(user)  # need new RAW password to re-create cipher and re-encrypt
        else:
            # No new password detected
            logger.debug(f'User {user.username} is updating their profile without a password change.')
            pass
