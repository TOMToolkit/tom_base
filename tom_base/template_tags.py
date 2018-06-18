from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def tom_setting(name):
    return settings.TOM_SETTINGS.get(name)


@register.simple_tag
def verbose_name(instance, field_name):
    return instance._meta.get_field(field_name).verbose_name.title()
