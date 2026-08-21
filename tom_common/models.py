from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    """Profile model for a TOMToolkit User."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=32, null=True, blank=True)

    # When the user last set their password. None means "not known to be current".
    password_changed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.user.username} Profile'
