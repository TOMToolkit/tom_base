from guardian.shortcuts import get_objects_for_user

from tom_targets.models import Target


def targets_for_user(user, qs, action):
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
        return qs.exclude(permissions__in=[Target.Permissions.PUBLIC, Target.Permissions.PRIVATE])
