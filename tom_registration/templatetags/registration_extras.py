from django import template
from django.conf import settings
from django.shortcuts import reverse

register = template.Library()

try:
    REGISTRATION_FLOW = settings.REGISTRATION_FLOW
except:
    REGISTRATION_FLOW = settings.REGISTRATION_FLOWS.ADMIN_REGISTRATION_ONLY


@register.inclusion_tag('tom_registration/partials/register_button.html')
def registration_button():
    """

    """
    url = reverse('home')
    user_self_registration = (REGISTRATION_FLOW != settings.REGISTRATION_FLOWS.ADMIN_REGISTRATION_ONLY)
    if user_self_registration:
        url = reverse('registration:register')
    return {
        'user_self_registration': user_self_registration,
        'url_from_context': url  # TODO: comment this
    }