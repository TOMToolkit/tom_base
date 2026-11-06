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


class TermsOfServiceAcceptance(models.Model):
    """A user's acceptance of one version of this TOM's terms of service.

    The current version is the TOM_TERMS_OF_SERVICE_VERSION setting; bumping it makes every
    user accept again, each acceptance keeping its own row for the audit trail.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='terms_acceptances')
    version = models.CharField(max_length=100)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'version'], name='unique_terms_acceptance_per_version'),
        ]

    def __str__(self) -> str:
        return f'{self.user.username} accepted terms version {self.version}'
