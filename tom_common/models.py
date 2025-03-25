from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session


class Profile(models.Model):
    """Profile model for a TOMToolkit User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'


class UserSession(models.Model):
    """Mapping model to associate the User and their Sessions

    An instance of this model is created whenever we receive the user_logged_in
    signal (see signals.py). Upon receiving user_logged_out, we delete all instances
    of UserSession for the specific User logging out.

    This allows us to manage the User's encrypted data in their app profiles,
    should they change their password (see signals.py).
    """
    # if either of the referenced objects are deleted, delete this object (CASCADE).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)

    def __str__(self):
        return f'UserSession for {self.user.username} with Session key {self.session.session_key}'

