from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    """Profile model for a TOMToolkit User."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.user.username} Profile'
