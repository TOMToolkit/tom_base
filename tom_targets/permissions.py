from guardian.shortcuts import get_objects_for_user

from tom_targets.models import Target


def targets_for_user(user, qs, action):
    """
    This is a wrapper function for django-guardian's get_objects_for_user function
    that attempts to mitigate performance issues with TOMs that have large targets
    that are not private. It works by splitting the queryset into private and public
    targets and then checking permissions only for the private targets.

    :param user: The user for whom to retrieve targets.
    :type user: User

    :param qs: The queryset of targets to filter.
    :type qs: QuerySet

    :param action: The action to check permissions for.
    :type action: str

    :returns: The filtered queryset of targets.
    """
    assert action in ['view_target', 'change_target', 'delete_target']

    if user.is_authenticated:
        if user.is_superuser:
            # Do not filter the queryset by permissions at all
            return qs
        else:
            # Exclude targets that are private except for those that the user has explicit permissions to view
            private_targets = qs.filter(permissions=Target.Permissions.PRIVATE)
            public_targets = qs.exclude(permissions=Target.Permissions.PRIVATE)
            return public_targets | get_objects_for_user(user, f'{Target._meta.app_label}.{action}', private_targets)
    else:
        # Only allow open targets
        return qs.filter(permissions=Target.Permissions.OPEN)
