from rest_framework import serializers

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
                                                      'semimajor_axis')
                     ]

    def create(self, validated_data):
        """DRF requires explicitly handling writeable nested serializers,
        here we pop the alias/tag data and save it using their respective
        serializers
        """
        aliases = validated_data.pop('aliases', [])
        targetextras = validated_data.pop('targetextra_set', [])

        target = Target.objects.create(**validated_data)

        tns = TargetNameSerializer(data=aliases, many=True)
        if tns.is_valid():
            tns.save(target=target)

        tes = TargetExtraSerializer(data=targetextras, many=True)
        if tes.is_valid():
            tes.save(target=target)

        return target


    def update(self, instance, validated_data):
        """
        For TargetExtra and TargetName objects, if the ID is present, it will update the corresponding row. If the ID is 
        not present, it will attempt to create a new TargetExtra or TargetName associated with this Target.
        """
        aliases = validated_data.pop('aliases', [])
        targetextras = validated_data.pop('targetextra_set', [])

        instance.name = validated_data.get('name', instance.name)
        instance.type = validated_data.get('type', instance.type)
        instance.ra = validated_data.get('ra', instance.ra)
        instance.dec = validated_data.get('dec', instance.dec)
        instance.epoch = validated_data.get('epoch', instance.epoch)
        instance.parallax = validated_data.get('parallax', instance.parallax)
        instance.pm_ra = validated_data.get('pm_ra', instance.pm_ra)
        instance.pm_dec = validated_data.get('pm_dec', instance.pm_dec)
        instance.galactic_lng = validated_data.get('galactic_lng', instance.galactic_lng)
        instance.galactic_lat = validated_data.get('galactic_lat', instance.galactic_lat)
        instance.distance = validated_data.get('distance', instance.distance)
        instance.distance_err = validated_data.get('distance_err', instance.distance_err)
        instance.scheme = validated_data.get('scheme', instance.scheme)
        instance.epoch_of_elements = validated_data.get('epoch_of_elements', instance.epoch_of_elements)
        instance.mean_anomaly = validated_data.get('mean_anomaly', instance.mean_anomaly)
        instance.arg_of_perihelion = validated_data.get('arg_of_perihelion', instance.arg_of_perihelion)
        instance.eccentricity = validated_data.get('eccentricity', instance.eccentricity)
        instance.lng_asc_node = validated_data.get('lng_asc_node', instance.lng_asc_node)
        instance.inclination = validated_data.get('inclination', instance.inclination)
        instance.mean_daily_motion = validated_data.get('mean_daily_motion', instance.mean_daily_motion)
        instance.semimajor_axis = validated_data.get('semimajor_axis', instance.semimajor_axis)
        instance.epoch_of_perihelion = validated_data.get('epoch_of_perihelion', instance.epoch_of_perihelion)
        instance.ephemeris_period = validated_data.get('ephemeris_period', instance.ephemeris_period)
        instance.ephemeris_period_err = validated_data.get('ephemeris_period_err', instance.ephemeris_period_err)
        instance.ephemeris_epoch = validated_data.get('ephemeris_epoch', instance.ephemeris_epoch)
        instance.ephemeris_epoch_err = validated_data.get('ephemeris_epoch_err', instance.ephemeris_epoch_err)
        instance.perihdist = validated_data.get('perihdist', instance.perihdist)
        instance.save()

        # TODO: updating an existing TargetName with the same value results in an integrity error
        for alias_data in aliases:
            alias = dict(alias_data)
            if alias.get('id'):
                tn_instance = TargetName.objects.get(pk=alias['id'])
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

        return instance
