from django import template

from tom_calendar.utils import target_list_color as _target_list_color

register = template.Library()


@register.simple_tag
def target_list_color(target_list):
    return _target_list_color(target_list)
