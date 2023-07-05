from django.conf import settings
from django.contrib.auth.models import Group
from guardian.shortcuts import assign_perm, get_groups_with_perms
from rest_framework import serializers

from tom_common.serializers import GroupSerializer
from tom_dataproducts.models import DataProductGroup, DataProduct, ReducedDatum
from tom_observations.models import ObservationRecord
from tom_observations.serializers import ObservationRecordFilteredPrimaryKeyRelatedField
from tom_targets.models import Target
from tom_targets.serializers import TargetFilteredPrimaryKeyRelatedField


class DataProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataProductGroup
        fields = ('name', 'created', 'modified')


class ReducedDatumSerializer(serializers.ModelSerializer):
    target = TargetFilteredPrimaryKeyRelatedField(queryset=Target.objects.all())

    class Meta:
        model = ReducedDatum
        fields = (
            'data_product',
            'data_type',
            'source_name',
            'source_location',
            'timestamp',
            'value',
            'target'
        )

    def create(self, validated_data):
        """DRF requires explicitly handling writeable nested serializers,
        here we pop the groups data and save it using its serializer.
        """
        groups = validated_data.pop('groups', [])

        rd = ReducedDatum(**validated_data)
        rd.full_clean()
        rd.save()

        # Save groups for this target
        group_serializer = GroupSerializer(data=groups, many=True)
        if group_serializer.is_valid() and settings.TARGET_PERMISSIONS_ONLY is False:
            for group in groups:
                group_instance = Group.objects.get(pk=group['id'])
                assign_perm('tom_dataproducts.view_dataproduct', group_instance, rd)
                assign_perm('tom_dataproducts.change_dataproduct', group_instance, rd)
                assign_perm('tom_dataproducts.delete_dataproduct', group_instance, rd)

        return rd


class DataProductSerializer(serializers.ModelSerializer):
    target = TargetFilteredPrimaryKeyRelatedField(queryset=Target.objects.all())
    observation_record = ObservationRecordFilteredPrimaryKeyRelatedField(queryset=ObservationRecord.objects.all(),
                                                                         required=False)
    groups = GroupSerializer(many=True, required=False)
    data_product_group = DataProductGroupSerializer(many=True, required=False)
    reduceddatum_set = ReducedDatumSerializer(many=True, required=False)
    data_product_type = serializers.CharField(allow_blank=False)

    class Meta:
        model = DataProduct
        fields = (
            'id',
            'product_id',
            'target',
            'observation_record',
            'data',
            'extra_data',
            'data_product_type',
            'groups',
            'data_product_group',
            'reduceddatum_set'
        )

    def create(self, validated_data):
        """DRF requires explicitly handling writeable nested serializers,
        here we pop the groups data and save it using its serializer.
        """

        groups = validated_data.pop('groups', [])

        dp = DataProduct.objects.create(**validated_data)

        # Save groups for this target
        group_serializer = GroupSerializer(data=groups, many=True)
        if group_serializer.is_valid() and settings.TARGET_PERMISSIONS_ONLY is False:
            for group in groups:
                group_instance = Group.objects.get(pk=group['id'])
                assign_perm('tom_dataproducts.view_dataproduct', group_instance, dp)
                assign_perm('tom_dataproducts.change_dataproduct', group_instance, dp)
                assign_perm('tom_dataproducts.delete_dataproduct', group_instance, dp)

        return dp

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        groups = []
        for group in get_groups_with_perms(instance):
            groups.append(GroupSerializer(group).data)
        representation['groups'] = groups
        return representation

    def update(self, instance, validated_data):
        groups = validated_data.pop('groups', [])

        super().save(instance, validated_data)

        # Save groups for this dataproduct
        group_serializer = GroupSerializer(data=groups, many=True)
        if group_serializer.is_valid() and not settings.TARGET_PERMISSIONS_ONLY:
            for group in groups:
                group_instance = Group.objects.get(pk=group['id'])
                assign_perm('tom_dataproducts.view_dataproduct', group_instance, instance)
                assign_perm('tom_dataproducts.change_dataproduct', group_instance, instance)
                assign_perm('tom_dataproducts.delete_dataproduct', group_instance, instance)

        return instance

    def validate_data_product_type(self, value):
        for dp_type in settings.DATA_PRODUCT_TYPES.keys():
            if not value or value == dp_type:
                break
        else:
            raise serializers.ValidationError('Not a valid data_product_type. Valid data_product_types are {0}.'
                                              .format(', '.join(k for k in settings.DATA_PRODUCT_TYPES.keys())))
        return value
