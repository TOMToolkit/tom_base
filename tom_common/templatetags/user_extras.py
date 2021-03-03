from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.inclusion_tag('auth/partials/group_list.html', takes_context=True)
def group_list(context):
    print('groups')
    return {
        'request': context['request'],
        'groups': Group.objects.all().exclude(name='Public')
    }


# @register.inclusion_tag('auth/partials/user_list.html', takes_context=True)
# def 
