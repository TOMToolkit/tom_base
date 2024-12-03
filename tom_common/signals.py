from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from tom_common.models import Profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """When a new user is created, create a profile for them."""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    """When a user is saved, save their profile."""
    # Take advantage of the fact that logging in updates a user's last_login field
    # to create a profile for users that don't have one.
    try:
        instance.profile.save()
    except User.profile.RelatedObjectDoesNotExist:
        Profile.objects.create(user=instance)
