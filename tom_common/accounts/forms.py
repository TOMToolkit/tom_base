"""The sign-up form extras django-allauth adds to its own SignupForm.

allauth composes ``ACCOUNT_SIGNUP_FORM_CLASS`` into its ``SignupForm``: our fields appear on
the sign-up page alongside allauth's username/email/password fields, and after the user is
created allauth calls ``signup(request, user)`` for us to store them. A TOM adds fields by
subclassing this and re-pointing ``ACCOUNT_SIGNUP_FORM_CLASS``.
"""
from __future__ import annotations

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from tom_common.models import TermsOfServiceAcceptance


class TomSignupForm(forms.Form):
    """First/last name and the Profile fields; optional unless listed in TOM_REQUIRED_USER_FIELDS."""
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    affiliation = forms.CharField(max_length=100, required=False, label='Organization / affiliation')
    phone_number = forms.CharField(max_length=32, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # update forms.Fields attributes according to configuration
        for field_name in getattr(settings, 'TOM_REQUIRED_USER_FIELDS', []):
            if field_name in self.fields:
                self.fields[field_name].required = True
        # with a terms-of-service version configured, signing up includes accepting it
        if getattr(settings, 'TOM_TERMS_OF_SERVICE_VERSION', None):
            self.fields['accept_terms'] = forms.BooleanField(
                required=True,
                label=format_html('I accept the <a href="{}" target="_blank">terms of service</a>',
                                  reverse('terms-of-service')),
            )

    def signup(self, request: HttpRequest, user: User) -> None:
        """Store this form's fields; called by allauth after it has created the user."""
        # imported here to avoid importing view code at form-import time
        from tom_common.accounts.views import _client_ip

        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.save(update_fields=['first_name', 'last_name'])

        profile = user.profile  # created by the post_save signal when allauth saved the user
        profile.affiliation = self.cleaned_data.get('affiliation') or None
        profile.phone_number = self.cleaned_data.get('phone_number') or None
        profile.save(update_fields=['affiliation', 'phone_number'])

        if self.cleaned_data.get('accept_terms'):
            TermsOfServiceAcceptance.objects.get_or_create(
                user=user, version=settings.TOM_TERMS_OF_SERVICE_VERSION,
                defaults={'ip_address': _client_ip(request)},
            )
