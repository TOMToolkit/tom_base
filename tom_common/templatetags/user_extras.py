import logging

from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.mfa.adapter import get_adapter as get_mfa_adapter
from allauth.mfa.models import Authenticator
from guardian.conf import settings as guardian_settings

from django import template
from django.conf import settings
from django.contrib.auth.models import Group, User

from tom_common.accounts.email import email_is_configured
from tom_common.accounts.requirements import AccountRequirement
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
        'groups': Group.objects.all()
    }


@register.inclusion_tag('auth/partials/user_list.html', takes_context=True)
def user_list(context):
    """
    Renders the list of users in the TOM along with edit/delete/change password buttons, as well as an Add User button.

    Each configured account requirement contributes a column (label + the set of pks
    meeting it) so administrators can see who is not yet compliant.
    """
    # guardian's anonymous user is a permissions sentinel, not a person: requirements are
    # inapplicable to it (it never logs in), so it belongs in no list of users
    users = list(User.objects.select_related('profile')
                 .exclude(username=guardian_settings.ANONYMOUS_USER_NAME))
    requirement_columns = []
    for dotted_path in getattr(settings, 'TOM_ACCOUNT_REQUIREMENTS', []):
        requirement = import_string(dotted_path)
        if isinstance(requirement, AccountRequirement) and requirement.is_configured():
            requirement_columns.append({
                'label': requirement.column_label(),
                'met_pks': requirement.met_user_pks(users),
            })
    return {
        'request': context['request'],
        'users': users,
        # users with an authenticator app enrolled, for the two-factor column
        'mfa_user_ids': set(
            Authenticator.objects.filter(type=Authenticator.Type.TOTP).values_list('user_id', flat=True)
        ),
        'requirement_columns': requirement_columns,
    }


@register.inclusion_tag('auth/partials/app_user_lists.html', takes_context=True)
def include_app_user_lists(context):
    """
    Imports the user list content from relevant apps into the template.

    Each user_list should be contained in a list of dictionaries in an app's apps.py `user_lists` method.
    Each user_list dictionary should contain a 'context' key with the path to the context processor class (typically a
    templatetag), and a 'partial' key with the path to the html partial template.

    FOR EXAMPLE:
    [{'partial': 'path/to/partial.html',
      'context': 'path/to/context/data/method'}]
    """
    user_lists_to_display = []
    for app in apps.get_app_configs():
        try:
            user_lists = app.user_lists()
        except AttributeError:
            continue
        if user_lists:
            for app_users in user_lists:
                try:
                    context_method = import_string(app_users['context'])
                except ImportError as e:
                    logger.warning(f'WARNING: Could not import context for {app.name} user list from '
                                   f'{app_users["context"]}.\n'
                                   f'{e}')
                    continue
                new_context = context_method(context)
                user_lists_to_display.append({'partial': app_users['partial'], 'context': new_context})

    context['user_lists_to_display'] = user_lists_to_display
    return context


@register.simple_tag(takes_context=True)
def mfa_can_be_disabled(context):
    """Whether the current user may disable their own authenticator app (the MFA adapter decides)."""
    user = context['request'].user
    authenticator = Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).first()
    return authenticator is None or get_mfa_adapter().can_delete_authenticator(authenticator)


@register.simple_tag(takes_context=True)
def registration_is_open(context):
    """Whether self-registration is currently open; the account adapter decides.

    Asking the adapter (rather than reading TOM_REGISTRATION_STRATEGY directly) keeps the
    Register button honest for TOMs that override is_open_for_signup in a custom adapter.
    """
    return get_account_adapter().is_open_for_signup(context['request'])


@register.inclusion_tag('auth/partials/pending_users.html', takes_context=True)
def pending_users_list(context):
    """The registrations awaiting approval, for the Pending users table on the Users page.

    "Pending" is literally ``is_active=False`` (tom_registration's convention), so an
    account an administrator deactivated by hand appears here too.
    """
    request = context['request']
    if not request.user.is_superuser:
        return {'request': request, 'pending_users': User.objects.none()}
    return {
        'request': request,
        'pending_users': User.objects.filter(is_active=False)
                                     .exclude(username=guardian_settings.ANONYMOUS_USER_NAME),
        'email_configured': email_is_configured(),
    }


@register.inclusion_tag('tom_common/partials/security_card.html')
def security_card(user):
    """Two-factor authentication status and actions for the Security card on the profile page."""
    totp_authenticator = Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).first()
    return {
        'user': user,
        'mfa_enabled': totp_authenticator is not None,
        'can_disable': get_mfa_adapter().can_delete_authenticator(totp_authenticator) if totp_authenticator else True,
    }


@register.inclusion_tag('tom_common/partials/user_data.html')
def user_data(user):
    """
    Returns the user information as a dictionary.
    """

    exclude_fields = ['password', 'last_login', 'id', 'is_active', 'user']
    user_dict = model_to_dict(user, exclude=exclude_fields)
    profile_dict = model_to_dict(user.profile, exclude=exclude_fields)

    # Get the auth_token from the Python descriptor attached (at runtime)
    # to the User model by Django as a reverse relation (the related_name)
    # to the rest_framework.authtoken.models.Token
    drf_api_token = getattr(user, 'auth_token', None)

    user_data = {
        'user': user,
        'profile': user.profile,
        'user_data': user_dict,
        'profile_data': profile_dict,
        'drf_api_token': drf_api_token,
    }
    return user_data


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
