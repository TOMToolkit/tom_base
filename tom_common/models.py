from django.conf import settings
from django.db.models.signals import post_save
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


class Profile(models.Model):
    """Profile model for a TOMToolkit User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'
