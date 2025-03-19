import logging

from django.conf import settings

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver

from rest_framework.authtoken.models import Token

from tom_common.models import Profile

logger = logging.getLogger(__name__)


# Signal: create DRF token for new users
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


# Signal: create Profile for new users
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
