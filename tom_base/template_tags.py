from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def tom_setting(name):
    return settings.TOM_SETTINGS.get(name)
