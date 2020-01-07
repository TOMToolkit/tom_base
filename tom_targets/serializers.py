from rest_framework import serializers
from .models import Target, TargetExtra, TargetName


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
