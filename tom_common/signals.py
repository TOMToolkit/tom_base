import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from rest_framework.authtoken.models import Token

from tom_common.models import Profile

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# NOTE: there are two ways to reference the User model: settings.AUTH_USER_MODEL and get_user_model()
# see https://docs.djangoproject.com/en/stable/topics/auth/customizing/#referencing-the-user-model
# Basically, settings.AUTH_USER_MODEL is for code that is executed upon import,
# while get_user_model() is valid after INSTALLED_APPS are loaded.


# Signal: Ensure every User has a Profile.
@receiver(post_save, sender=User)
def save_profile_on_user_post_save(sender, instance, created, **kwargs) -> None:
    """Guarantee the saved User has an associated :class:`Profile`.

    On creation, ``CustomUserCreationForm``'s inline Profile formset may
    have pre-attached a pk=None Profile to ``instance.profile`` carrying
    form-supplied data like ``affiliation``; we honour that by saving it
    via the descriptor. Otherwise we create a bare Profile from scratch.

    On subsequent saves we do not write back ``instance.profile`` — the
    cached value can be stale (e.g. ``update_last_login`` fires this
    signal on every login). Concurrent out-of-band Profile updates would
    be clobbered by an unconditional save. So on non-creation saves we
    only ensure a Profile *exists* (legacy users from before the Profile
    model existed); we never write to one that's already there.
    """
    if created:
        try:
            instance.profile.save()
        except User.profile.RelatedObjectDoesNotExist:  # type: ignore[attr-defined]
            logger.info(f'No Profile found for {instance}. Creating Profile.')
            Profile.objects.create(user=instance)
        return

    # Non-creation save: just backfill a Profile if (somehow) missing.
    if not Profile.objects.filter(user=instance).exists():
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
