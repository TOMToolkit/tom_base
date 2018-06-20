from django import template
from django.conf import settings
from django_comments.models import Comment

register = template.Library()


@register.simple_tag
def tom_setting(name):
    return settings.TOM_SETTINGS.get(name)


@register.simple_tag
def verbose_name(instance, field_name):
    return instance._meta.get_field(field_name).verbose_name.title()


@register.inclusion_tag('comments/list.html')
def recent_comments(limit=10):
    return {'comment_list': Comment.objects.all().order_by('-submit_date')[:limit]}
