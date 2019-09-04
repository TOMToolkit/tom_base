from django import template
from django.conf import settings
from django_comments.models import Comment

register = template.Library()


@register.simple_tag
def comments_enabled():
    """
    Returns the TOM setting specifying whether or not comments are enabled

    :returns: True if comments enabled, False otherwise
    :rtype: boolean
    """
    try:
        return settings.COMMENTS_ENABLED
    except AttributeError:
        return True


@register.simple_tag
def verbose_name(instance, field_name):
    """
    Returns the more descriptive field name from a Django model field

    :param instance: model instance
    :type instance: Model

    :param field_name: Field name from which descriptive name is desired
    :type str:

    :returns: Descriptive field name
    :rtype: str
    """
    return instance._meta.get_field(field_name).verbose_name.title()


@register.inclusion_tag('comments/list.html')
def recent_comments(limit=10):
    """
    Returns the most recent comments in the TOM up to the given limit, or 10 if not specified

    :Keyword Arguments:
        * limit (`int`): maximum number of comments to return
    """
    return {'comment_list': Comment.objects.all().order_by('-submit_date')[:limit]}


@register.filter
def truncate_number(value):
    """
    Truncates a numerical value to three decimal places

    :param value: number to be truncated
    :type value: str, float, int

    :returns: Truncated number
    :rtype: str
    """
    try:
        return '%.3f' % value
    except Exception:
        return value
