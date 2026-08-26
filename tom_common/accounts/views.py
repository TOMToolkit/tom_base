"""Views for the terms-of-service pages.

The terms text itself is the ``tom_common/partials/terms_of_service_text.html`` template,
which a TOM overrides in its own ``templates/`` directory.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from tom_common.mixins import SuperuserRequiredMixin
from tom_common.models import TermsOfServiceAcceptance

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('tom_common.security')


def _client_ip(request: HttpRequest) -> str | None:
    """The client IP for the acceptance record.

    Interprets ALLAUTH_TRUSTED_PROXY_COUNT the same way django-allauth does for its rate
    limits (the last address X-Forwarded-For holds before the trusted proxies), so one
    setting keeps both features truthful behind a reverse proxy.
    """
    trusted_proxy_count = getattr(settings, 'ALLAUTH_TRUSTED_PROXY_COUNT', None)
    if trusted_proxy_count:
        addresses = [address.strip()
                     for address in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')
                     if address.strip()]
        if len(addresses) >= trusted_proxy_count:
            return addresses[-trusted_proxy_count]
    return request.META.get('REMOTE_ADDR')


class TermsOfServiceView(TemplateView):
    """The public, read-only terms-of-service page (/terms/)."""
    template_name = 'tom_common/terms_of_service.html'


class TermsAcceptView(LoginRequiredMixin, View):
    """Shows the terms and records the logged-in user's acceptance of the current version."""
    template_name = 'tom_common/terms_accept.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return TemplateView.as_view(template_name=self.template_name)(request)

    def post(self, request: HttpRequest) -> HttpResponse:
        version = getattr(settings, 'TOM_TERMS_OF_SERVICE_VERSION', None)
        if version:
            _, created = TermsOfServiceAcceptance.objects.get_or_create(
                user=request.user, version=version,
                defaults={'ip_address': _client_ip(request)},
            )
            if created:
                security_logger.info(f'Terms of service accepted: {request.user.username} '
                                     f'(version {version}, ip {_client_ip(request)})')
            messages.success(request, 'Thank you — your acceptance of the terms of service has been recorded.')
        return redirect(settings.LOGIN_REDIRECT_URL)


class UserApprovalView(SuperuserRequiredMixin, View):
    """Approves a registration awaiting approval (the Pending users table posts here)."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        # is_active=False in the lookup makes approval idempotent: re-posting 404s
        user = get_object_or_404(User, pk=pk, is_active=False)
        user.is_active = True
        user.save()
        security_logger.info(f'Registration approved: {user.username} by {request.user.username}')
        self._notify_user_of_approval(request, user)
        messages.success(request, f'{user.username} approved.')
        return redirect('user-list')

    @staticmethod
    def _notify_user_of_approval(request: HttpRequest, user: User) -> None:
        """Tell the applicant they can log in now; email must not break the approval."""
        if not user.email:
            return
        email_context = {
            'user': user,
            'tom_name': getattr(settings, 'TOM_NAME', 'TOM Toolkit'),
            'login_url': request.build_absolute_uri(reverse('account_login')),
        }
        try:
            send_mail(
                subject=render_to_string('account/email/registration_approved_subject.txt',
                                         email_context).strip(),
                message=render_to_string('account/email/registration_approved_message.txt',
                                         email_context),
                from_email=None,  # DEFAULT_FROM_EMAIL
                recipient_list=[user.email],
            )
        except Exception as error:
            logger.warning(f'Could not send the approval notification to {user.email}: {error}')
