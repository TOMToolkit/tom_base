from django import template
from django.contrib.auth.models import Group, User

register = template.Library()


@register.inclusion_tag('auth/partials/group_list.html', takes_context=True)
def group_list(context):
    """

    """
    return {
        'request': context['request'],
        'groups': Group.objects.all().exclude(name='Public')
    }


@register.inclusion_tag('auth/partials/user_list.html', takes_context=True)
def user_list(context):
    """

    """
    return {
        'request': context['request'],
        'users': User.objects.all()
    }
