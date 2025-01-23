import logging
from django import template
from django.contrib.auth.models import Group, User
from django.forms.models import model_to_dict
from django.apps import apps
from django.utils.module_loading import import_string

register = template.Library()
logger = logging.getLogger(__name__)


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


@register.inclusion_tag('tom_common/partials/app_profiles.html', takes_context=True)
def show_app_profiles(context, user):
    """
    Imports the profile content from relevant apps into the template.

    Each profile should be contained in a list of dictionaries in an app's apps.py `profile_details` method.
    Each profile dictionary should contain a 'context' key with the path to the context processor class (typically a
    templatetag), and a 'partial' key with the path to the html partial template.

    FOR EXAMPLE:
    [{'partial': 'path/to/partial.html',
      'context': 'path/to/context/data/method'}]
    """
    profiles_to_display = []
    for app in apps.get_app_configs():
        try:
            profile_details = app.profile_details()
        except AttributeError:
            continue
        if profile_details:
            for profile in profile_details:
                try:
                    context_method = import_string(profile['context'])
                except ImportError:
                    logger.warning(f'WARNING: Could not import context for {app.name} profile from '
                                   f'{profile["context"]}.\n'
                                   f'Are you sure you have the right path?')
                    continue
                new_context = context_method(user)
                profiles_to_display.append({'partial': profile['partial'], 'context': new_context})

    context['user'] = user
    context['profiles_to_display'] = profiles_to_display
    return context


@register.inclusion_tag('tom_common/partials/include_profile_card.html', takes_context=True)
def show_individual_app_profile(context, profile_data):
    """
    An Inclusion tag for setting the unique context for each app's user profile.
    """
    for item in profile_data['context']:
        context[item] = profile_data['context'][item]
    context['profile_partial'] = profile_data['partial']
    return context
