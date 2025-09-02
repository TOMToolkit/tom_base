import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from rest_framework.authtoken.models import Token

from tom_common.models import Profile, UserSession
from tom_common import session_utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# NOTE: there are two ways to reference the User model: settings.AUTH_USER_MODEL and get_user_model()
# see https://docs.djangoproject.com/en/stable/topics/auth/customizing/#referencing-the-user-model
# Basically, settings.AUTH_USER_MODEL is for code that is executed upon import,
# while get_user_model() is valid after INSTALLED_APPS are loaded.


# Signal: Create a Profile for the User when the User instance is created
@receiver(post_save, sender=User)
def save_profile_on_user_post_save(sender, instance, **kwargs):
    """When a user is saved, save their profile."""
    # Take advantage of the fact that logging in updates a user's last_login field
    # to create a profile for users that don't have one.
    try:
        instance.profile.save()
    except User.profile.RelatedObjectDoesNotExist:  # type: ignore
        logger.info(f'No Profile found for {instance}. Creating Profile.')
        Profile.objects.create(user=instance)


# Signal: Create a DRF token for the User when the User instance is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token_on_user_post_save(sender, instance=None, created=False, **kwargs):
    """Create a token for the User when the User instance is created.

    This is the API token used by the User to authenticate with the
    Django REST framework API.

    For more information, see the Django REST framework documentation:
    https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication
    """
    if created:
        Token.objects.create(user=instance)


# Signal: Create UserSession on login
@receiver(user_logged_in)
def create_user_session_on_user_logged_in(sender, request, user, **kwargs) -> None:
    """Whenever a user logs in, create a UserSession instance to associate
    the User with the new Session.
    """
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
    logger.debug(f"User {user.username} has logged in. request: {request}")

    password = request.POST.get("password")  # Capture password from login
    if password:
        encryption_key: bytes = session_utils.create_cipher_encryption_key(user, password)
        session_utils.save_key_to_session_store(encryption_key, request.session)
    else:
        logger.error(f'User {user.username} logged in without a password. Cannot create encryption key.')


# Signal: Clear cipher encryption key on logout
@receiver(user_logged_out)
def clear_encryption_key_on_user_logged_out(sender, request, user, **kwargs) -> None:
    """Clear the cipher encryption key when a user logs out.
    """
    if user:
        logger.debug(f'User {user.username} has logged out. Deleting key from Session.'
                     f'sender: {sender}; request: {request}')
        request.session.pop(session_utils.SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY, None)


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
     * re-encrypt the user's sensitive data (see session_utils.reencrypt_data() function)
     *
    """
    logger.debug(f"kwargs: {kwargs}")
    user = kwargs.get("instance", None)

    if user and not user.username == 'AnonymousUser' and not user.is_anonymous:
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
            logger.debug(f'User {user.username} is changing their password.')
            session_utils.reencrypt_data(user)  # need new RAW password to re-create cipher and re-encrypt
        else:
            # No new password detected
            logger.debug(f'User {user.username} is updating their profile without a password change.')
