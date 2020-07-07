from rest_framework import serializers

from tom_targets.models import Target, TargetExtra, TargetName
from tom_targets.validators import RequiredFieldsTogetherValidator


class TargetNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetName
        fields = ('name',)


class TargetExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetExtra
        fields = ('key', 'value')


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
        here we pop the alias/tag data and save it using thier respective
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
