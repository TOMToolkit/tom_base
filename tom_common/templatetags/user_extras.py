from django import template
from django.contrib.auth.models import Group, User
from django.forms.models import model_to_dict

register = template.Library()


@register.inclusion_tag('auth/partials/group_list.html', takes_context=True)
def group_list(context):
    """
    Renders the list of groups in the TOM along with edit/delete buttons, as well as an Add Group button.
    """
    return {
        'request': context['request'],
        'groups': Group.objects.all().exclude(name='Public')
    }


@register.inclusion_tag('auth/partials/user_list.html', takes_context=True)
def user_list(context):
    """
    Renders the list of users in the TOM along with edit/delete/change password buttons, as well as an Add User button.
    """
    return {
        'request': context['request'],
        'users': User.objects.all()
    }


@register.inclusion_tag('tom_common/partials/user_data.html')
def user_data(user):
    """
    Returns the user information as a dictionary.
    """
    exlcude_fields = ['password', 'last_login', 'id', 'is_active']
    user_fields = [field.name for field in user._meta.fields if field.name not in exlcude_fields]
    return {
        'user': user,
        'profile_data': model_to_dict(user, fields=user_fields),
    }
