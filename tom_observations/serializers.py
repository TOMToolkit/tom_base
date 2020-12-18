from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from rest_framework import serializers

from tom_observations.models import ObservationRecord


class ObservationRecordFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    # This PrimaryKeyRelatedField subclass is used to implement get_queryset based on the permissions of the user
    # submitting the request. The pattern was taken from this StackOverflow answer: https://stackoverflow.com/a/32683066

    def get_queryset(self):
        request = self.context.get('request', None)
        queryset = super().get_queryset()
        if not (request and queryset):
            return None
        if settings.TARGET_PERMISSIONS_ONLY:
            return ObservationRecord.objects.all()
        else:
            return get_objects_for_user(request.user, 'tom_observations.change_observation')
