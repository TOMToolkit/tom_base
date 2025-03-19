from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    """Profile model for a TOMToolkit User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'
