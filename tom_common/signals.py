import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from rest_framework.authtoken.models import Token

from tom_common.models import Profile
from tom_common import session_utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# NOTE: there are two ways to reference the User model: settings.AUTH_USER_MODEL and get_user_model()
# see https://docs.djangoproject.com/en/stable/topics/auth/customizing/#referencing-the-user-model
# Basically, settings.AUTH_USER_MODEL is for code that is executed upon import,
# while get_user_model() is valid after INSTALLED_APPS are loaded.


# Signal: Create a Profile (with an encrypted DEK) for the User when the User instance is created
@receiver(post_save, sender=User)
def save_profile_on_user_post_save(sender, instance, created, **kwargs) -> None:
    """When a user is saved, ensure their Profile exists and has an encrypted DEK.

    On first save (user creation), creates a new Profile and generates an
    encrypted Data Encryption Key (DEK) for the user. The DEK is a random
    Fernet key encrypted by the server-side master key — see
    ``session_utils.create_encrypted_dek()`` for details.

    On subsequent saves, just saves the existing Profile (e.g., to propagate
    any changes from inline formsets).
    """
    try:
        profile = instance.profile
        # If the Profile exists but has no DEK (e.g., it was created before
        # the encryption system was added), generate one now.
        if not profile.encrypted_dek:
            profile.encrypted_dek = session_utils.create_encrypted_dek()
        profile.save()
    except User.profile.RelatedObjectDoesNotExist:  # type: ignore[attr-defined]
        logger.info(f'No Profile found for {instance}. Creating Profile with encryption key.')
        Profile.objects.create(
            user=instance,
            encrypted_dek=session_utils.create_encrypted_dek(),
        )


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
