"""API views for token management.

Wraps DRF ObtainAuthToken view so that if MFA is required
for authentication, then it's also required to get and API Token.
(and elsewhere API tokens are revoked when MFA is turned on).

NOTE: separating this from ``api_auth`` avoids circular import.
"""
from __future__ import annotations

from django.conf import settings

from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response


class TomObtainAuthToken(ObtainAuthToken):
    """The api/token-auth/ endpoint; refuses when TOM_API_TOKEN_REQUIRES_MFA.

    The ``api/token-auth`` endpoint returns an API token for a password, but
    with MFA turned on, that represents an escalation (i.e. API token for
    a password + TOTP). For now, we disable the endpoint when MFA is configured.
    """

    def post(self, request, *args, **kwargs):
        if getattr(settings, 'TOM_API_TOKEN_REQUIRES_MFA', False):
            return Response(
                {'detail': 'This endpoint is disabled because API tokens on this TOM require '
                           'two-factor authentication. Log in on the web and copy your token '
                           'from your profile page.'},
                status=status.HTTP_403_FORBIDDEN)
        return super().post(request, *args, **kwargs)
