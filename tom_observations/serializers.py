from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.query import QuerySet
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import serializers

from tom_common.serializers import GroupSerializer
from tom_observations.models import ObservationGroup, ObservationRecord


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
    groups = GroupSerializer(many=True, required=False)  # TODO: return groups in detail and list
    observation_groups = ObservationGroupField(many=True, read_only=True, source='observationgroup_set')
    status = serializers.CharField(required=False)

    class Meta:
        model = ObservationRecord
        fields = '__all__'

    def create(self, validated_data):
        groups = validated_data.pop('groups', [])

        obsr = ObservationRecord.objects.create(**validated_data)

        group_serializer = GroupSerializer(data=groups, many=True)
        if group_serializer.is_valid() and settings.TARGET_PERMISSIONS_ONLY is False:
            for group in groups:
                group_instance = Group.objects.get(pk=group['id'])
                assign_perm('tom_observations.view_observationrecord', group_instance, obsr)
                assign_perm('tom_observations.change_observationrecord', group_instance, obsr)
                assign_perm('tom_observations.delete_observationrecord', group_instance, obsr)

        return obsr


class ObservationRecordFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    # This PrimaryKeyRelatedField subclass is used to implement get_queryset based on the permissions of the user
    # submitting the request. The pattern was taken from this StackOverflow answer: https://stackoverflow.com/a/32683066

    def get_queryset(self) -> QuerySet:
        request = self.context.get('request', None)
        queryset = super().get_queryset()
        if not (request and queryset):
            return None
        if settings.TARGET_PERMISSIONS_ONLY:
            return ObservationRecord.objects.all()
        else:
            return get_objects_for_user(request.user, 'tom_observations.change_observation')
