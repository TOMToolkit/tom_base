from django import template
from django.conf import settings
from django.contrib.auth.models import User
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

@register.inclusion_tag('tom_registration/partials/pending_users.html', takes_context=True)
def pending_users(context):
    return {
        'request': context['request'],  # TODO: should this live in the user_list.html template?
        'users': User.objects.filter(is_active=False)
    }
