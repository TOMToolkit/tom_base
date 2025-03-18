import base64
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from rest_framework.authtoken.models import Token

from tom_common.models import Profile

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# NOTE: there are two ways to reference the User model,
# see https://docs.djangoproject.com/en/stable/topics/auth/customizing/#referencing-the-user-model
# Basically, settings.AUTH_USER_MODEL is for code that is executed upon import,
# while get_user_model() is valid after INSTALLED_APPS are loaded.


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    """When a user is saved, save their profile."""
    # Take advantage of the fact that logging in updates a user's last_login field
    # to create a profile for users that don't have one.
    try:
        instance.profile.save()
    except User.profile.RelatedObjectDoesNotExist:
        logger.info(f'No Profile found for {instance}. Creating Profile.')
        Profile.objects.create(user=instance)


# Signal: Create a token for the User when the User instance is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    """Create a token for the User when the User instance is created.

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

def get_session_cipher(user) -> Fernet:
    """Return the User's Fernet cipher"""
    cipher = user.request.session.get('cipher')
    if cipher:
        return Fernet(cipher)
    return None


def create_cipher(user, password: str) -> Fernet:
    """Create a Fernet cipher and save it to be used to encrypt API keys and
    other external service credentials for this User. Uses their login password
    to generate the encryption_key.

    see https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
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
    encryption_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

    cipher = Fernet(encryption_key)  # create cipher
    return cipher


# Signal: Set cipher on login
@receiver(user_logged_in)
def set_cipher_on_login(sender, request, user, **kwargs) -> None:
    """When the user logs in, capture their password and use it to
    generate a cipher (Fernet instance). Save it in the User's Session.

    The cipher will be used to encrypt/decrypt sensitive user data (passwords
    and API keys).
    """
    logger.debug(f"User {user.username} has logged in. sender: {sender}; request: {request}")

    if hasattr(user, "profile"):
        password = request.POST.get("password")  # Capture password from login
        if password:
            logger.debug(f"Creating cipher for user: {user.username} with password {password}")
            cipher = create_cipher(user, password)
            request.session['cipher'] = cipher  # save cipher in session


# Signal: Clear cipher on logout
@receiver(user_logged_out)
def clear_cipher_on_logout(sender, request, user, **kwargs) -> None:
    """Clear the cipher when a user logs out."""
    logger.debug(f"User {user.username} has logged out. sender: {sender}; request: {request}")
    # examine cipher before clearing it
    cipher = request.session.get('cipher')
    if cipher:
        logger.debug(f'Cipher exists ({cipher}), proceeding to clear it.')
    request.session.pop('cipher', None)


def reencrypt_sensitive_data(password):
    """Re-encrypt the user's sensitive data with the new password."""
    logger.debug("Re-encrypting sensitive data...")
    logger.debug("re-create cipher")
    # TODO: create mechanism for know what the sensitive data Fields are across all INSTALLTED_APPs and their models
    logger.debug("use new cipher to re-encrypt data")
    logger.debug("save newly re-encrypted data")
    logger.debug("save save new cipher in Session")


# Signal: Update the User's sensitive data when the password changes
@receiver(pre_save, sender=get_user_model())
def user_updated(sender, instance, **kwargs):
    """When the User model is saved, detect if the password has changed.

    Current list of actions to be taken upon User password change:
     * re-encrypt the user's sensitive data with the new password
     *
    """
    # TODO: sort out what the signiture of the receiver should be
    user = kwargs.get("instance", None)

    if user:
        # user.password vs. user._password:
        # the user.password field is used for authentication (via comparison to the (hashed) password
        # being tested for validity). The _password field is the raw password and is what we need to
        # create a new cipher for the User's sensitive data.

        # This Signal is called for ANY change to the User model, not just password changes.
        # So, determine if the password has changed by comparing new and old (hashed) passwords.
        new_hashed_password = user.password  # from the not-yet-saved User instance
        try:
            old_hashed_password = User.objects.get(id=user.id).password  # from the previously-saved User instance
        except User.DoesNotExist:
            old_hashed_password = None

        if new_hashed_password != old_hashed_password:
            # New password detected
            new_raw_password = user._password  # CAUTION: this is implemenation dependent (using _<property>)
            logger.debug(f'User {user.username} is changing their password to {new_raw_password}')
            reencrypt_sensitive_data(new_raw_password)  # need new RAW password to re-create cipher and re-encrypt
        else:
            # No new password detected
            logger.debug(f'User {user.username} is updating their profile without a password change.')
            pass