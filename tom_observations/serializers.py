import json

from django.conf import settings
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import serializers

from tom_observations.models import DynamicCadence, ObservationGroup, ObservationRecord


class DynamicCadenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicCadence
        fields = '__all__'

    def to_representation(self, value):
        return f'{value.cadence_strategy} with parameters {value.cadence_parameters}'


class ObservationGroupSerializer(serializers.ModelSerializer):
    dynamiccadence_set = DynamicCadenceSerializer(many=True, required=False)
    observationrecord_set = serializers.PrimaryKeyRelatedField(many=True, required=False, read_only=True)

    class Meta:
        model = ObservationGroup
        fields = '__all__'

    def create(self, validated_data):
        dynamic_cadences = validated_data.pop('dynamic_cadences')

        print(f'validated_data: {validated_data}')
        observation_groups = ObservationGroup.objects.bulk_create(**validated_data)

        dynamic_cadence_serializer = DynamicCadenceSerializer(data=dynamic_cadences, many=True)
        if dynamic_cadence_serializer.is_valid():
            dynamic_cadence_serializer.save()

        return observation_groups


class ObservationRecordSerializer(serializers.ModelSerializer):
    observationgroup_set = ObservationGroupSerializer(many=True, required=False)
    # put cadence as a value and handle it in create()

    class Meta:
        model = ObservationRecord
        fields = '__all__'

    def create(self, validated_data):
        observation_groups = validated_data.pop('observation_groups', [])

        observation_records = ObservationRecord.objects.bulk_create(**validated_data)

        observation_group_serializer = ObservationGroupSerializer(data=observation_groups, many=True)
        if observation_group_serializer.is_valid():
            observation_group_serializer.save(observation_records=observation_records)
            for og in observation_group_serializer.instance:
                assign_perm('tom_observations.view_observationgroup', self.request.user, og)
                assign_perm('tom_observations.change_observationgroup', self.request.user, og)
                assign_perm('tom_observations.delete_observationgroup', self.request.user, og)

        return observation_records

    def to_representation(self, instance):
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
