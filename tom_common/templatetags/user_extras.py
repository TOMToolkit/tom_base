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

    exclude_fields = ['password', 'last_login', 'id', 'is_active', 'user']
    user_dict = model_to_dict(user, exclude=exclude_fields)
    profile_dict = model_to_dict(user.profile, exclude=exclude_fields)
    return {
        'user': user,
        'profile': user.profile,
        'user_data': user_dict,
        'profile_data': profile_dict,
    }
