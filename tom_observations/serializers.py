import json

from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from rest_framework import serializers

from tom_observations.models import DynamicCadence, ObservationGroup, ObservationRecord


class ObservationGroupField(serializers.RelatedField):
    """
    ``RelatedField`` used to display ObservationGroups and DynamicCadences in a prettier fashion than offered by default
    DRF implementations.
    """
    def to_representation(self, instance: ObservationGroup) -> dict:
        return {
            'name': instance.name,
            'dynamic_cadences': [dc.__str__() for dc in instance.dynamiccadence_set.all()]
        }


class ObservationRecordSerializer(serializers.ModelSerializer):
    observation_groups = ObservationGroupField(many=True, read_only=True, source='observationgroup_set')

    class Meta:
        model = ObservationRecord
        fields = '__all__'

    def to_representation(self, instance):  # TODO: would it be better to just prettify the observation groups here
        representation = super().to_representation(instance)
        representation['parameters'] = json.loads(representation['parameters'])
        return representation


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
