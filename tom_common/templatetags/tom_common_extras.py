from django import template
from django.conf import settings
from django_comments.models import Comment

register = template.Library()


@register.simple_tag
def comments_enabled():
    try:
        return settings.COMMENTS_ENABLED
    except AttributeError:
        return True


@register.simple_tag
def verbose_name(instance, field_name):
    return instance._meta.get_field(field_name).verbose_name.title()


@register.inclusion_tag('comments/list.html')
def recent_comments(limit=10):
    return {'comment_list': Comment.objects.all().order_by('-submit_date')[:limit]}


@register.filter
def truncate_number(value):
    try:
        return '%.3f' % value
    except:
        return value
