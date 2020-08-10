from django.contrib.auth.models import Group
from guardian.shortcuts import assign_perm, get_groups_with_perms, get_objects_for_user
from rest_framework import serializers

from tom_common.serializers import GroupSerializer
from tom_targets.models import Target, TargetExtra, TargetName
from tom_targets.validators import RequiredFieldsTogetherValidator


class TargetNameSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = TargetName
        fields = ('id', 'name',)


class TargetExtraSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = TargetExtra
        fields = ('id', 'key', 'value')


class TargetSerializer(serializers.ModelSerializer):
    """Target serializer responsbile for transforming models to/from
    json (or other representations). See
    https://www.django-rest-framework.org/api-guide/serializers/#modelserializer
    """
    targetextra_set = TargetExtraSerializer(many=True)
    aliases = TargetNameSerializer(many=True)
    groups = GroupSerializer(many=True, required=False)  # TODO: return groups in detail and list

    class Meta:
        model = Target
        fields = '__all__'
        # TODO: We should investigate if this validator logic can be reused in the forms to reduce code duplication.
        # TODO: Try to put validators in settings to allow user changes
        validators = [RequiredFieldsTogetherValidator('type', 'SIDEREAL', 'ra', 'dec'),
                      RequiredFieldsTogetherValidator('type', 'NON_SIDEREAL', 'epoch_of_elements', 'inclination',
                                                      'lng_asc_node', 'arg_of_perihelion', 'eccentricity'),
                      RequiredFieldsTogetherValidator('scheme', 'MPC_COMET', 'perihdist', 'epoch_of_perihelion'),
                      RequiredFieldsTogetherValidator('scheme', 'MPC_MINOR_PLANET', 'mean_anomaly', 'semimajor_axis'),
                      RequiredFieldsTogetherValidator('scheme', 'JPL_MAJOR_PLANET', 'mean_daily_motion', 'mean_anomaly',
                                                      'semimajor_axis')]

    def create(self, validated_data):
        """DRF requires explicitly handling writeable nested serializers,
        here we pop the alias/tag/group data and save it using their respective
        serializers
        """

        aliases = validated_data.pop('aliases', [])
        targetextras = validated_data.pop('targetextra_set', [])
        groups = validated_data.pop('groups', [])

        target = Target.objects.create(**validated_data)

        # Save groups for this target
        group_serializer = GroupSerializer(data=groups, many=True)
        if group_serializer.is_valid():
            for group in groups:
                group_instance = Group.objects.get(pk=group['id'])
                assign_perm('tom_targets.view_target', group_instance, target)
                assign_perm('tom_targets.change_target', group_instance, target)
                assign_perm('tom_targets.delete_target', group_instance, target)

        tns = TargetNameSerializer(data=aliases, many=True)
        if tns.is_valid():
            for alias in aliases:
                if alias['name'] == target.name:
                    target.delete()
                    alias_value = alias['name']
                    raise serializers.ValidationError(
                        f'Alias \'{alias_value}\' conflicts with Target name \'{target.name}\'.')
            tns.save(target=target)

        tes = TargetExtraSerializer(data=targetextras, many=True)
        if tes.is_valid():
            tes.save(target=target)

        return target

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        groups = []
        for group in get_groups_with_perms(instance):
            groups.append(GroupSerializer(group).data)
        representation['groups'] = groups
        return representation

    def update(self, instance, validated_data):
        """
        For TargetExtra and TargetName objects, if the ID is present, it will update the corresponding row. If the ID is
        not present, it will attempt to create a new TargetExtra or TargetName associated with this Target.
        """
        aliases = validated_data.pop('aliases', [])
        targetextras = validated_data.pop('targetextra_set', [])
        groups = validated_data.pop('groups', [])

        # Save groups for this target
        group_serializer = GroupSerializer(data=groups, many=True)
        if group_serializer.is_valid():
            for group in groups:
                group_instance = Group.objects.get(pk=group['id'])
                assign_perm('tom_targets.view_target', group_instance, instance)
                assign_perm('tom_targets.change_target', group_instance, instance)
                assign_perm('tom_targets.delete_target', group_instance, instance)  # TODO: add tests

        for alias_data in aliases:
            alias = dict(alias_data)
            if alias['name'] == instance.name:  # Alias shouldn't conflict with target name
                alias_name = alias['name']
                raise serializers.ValidationError(
                    f'Alias \'{alias_name}\' conflicts with Target name \'{instance.name}\'.')
            if alias.get('id'):
                tn_instance = TargetName.objects.get(pk=alias['id'])
                if tn_instance.target != instance:  # Alias should correspond with target to be updated
                    raise serializers.ValidationError(f'''TargetName identified by id \'{tn_instance.id}\' is not an
                        alias of Target \'{instance.name}\'''')
                elif alias['name'] == tn_instance.name:
                    break  # Don't update if value doesn't change, because it will throw an error
                tns = TargetNameSerializer(tn_instance, data=alias_data)
            else:
                tns = TargetNameSerializer(data=alias_data)
            if tns.is_valid():
                tns.save(target=instance)

        for te_data in targetextras:
            te = dict(te_data)
            if te_data.get('id'):
                te_instance = TargetExtra.objects.get(pk=te['id'])
                tes = TargetExtraSerializer(te_instance, data=te_data)
            else:
                tes = TargetExtraSerializer(data=te_data)
            if tes.is_valid():
                tes.save(target=instance)

        fields_to_validate = ['name', 'type', 'ra', 'dec', 'epoch', 'parallax', 'pm_ra', 'pm_dec', 'galactic_lng',
                              'galactic_lat', 'distance', 'distance_err', 'scheme', 'epoch_of_elements',
                              'mean_anomaly', 'arg_of_perihelion', 'eccentricity', 'lng_asc_node', 'inclination',
                              'mean_daily_motion', 'semimajor_axis', 'epoch_of_perihelion', 'ephemeris_period',
                              'ephemeris_period_err', 'ephemeris_epoch', 'ephemeris_epoch_err', 'perihdist']
        for field in fields_to_validate:
            setattr(instance, field, validated_data.get(field, getattr(instance, field)))
        instance.save()

        return instance


class TargetFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    # This PrimaryKeyRelatedField subclass is used to implement get_queryset based on the permissions of the user
    # submitting the request. The pattern was taken from this StackOverflow answer: https://stackoverflow.com/a/32683066

    def get_queryset(self):
        request = self.context.get('request', None)
        queryset = super().get_queryset()
        if not (request and queryset):
            return None
        return get_objects_for_user(request.user, 'tom_targets.change_target')
