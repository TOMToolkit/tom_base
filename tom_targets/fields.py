from tom_targets.base_models import get_target_model_app_label
from guardian.shortcuts import get_objects_for_user
from rest_framework import serializers


class TargetFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    # This PrimaryKeyRelatedField subclass is used to implement get_queryset based on the permissions of the user
    # submitting the request. The pattern was taken from this StackOverflow answer: https://stackoverflow.com/a/32683066

    def get_queryset(self):
        request = self.context.get('request', None)
        queryset = super().get_queryset()
        if not (request and queryset):
            return None
        target_app_label = get_target_model_app_label()
        return get_objects_for_user(request.user, f'{target_app_label}.change_target')
