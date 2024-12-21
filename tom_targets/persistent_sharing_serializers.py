from rest_framework import serializers
from tom_dataproducts.sharing import get_sharing_destination_options
from tom_targets.sharing import share_target_and_all_data
from tom_targets.fields import TargetFilteredPrimaryKeyRelatedField
from tom_targets.models import PersistentShare, Target


class PersistentShareSerializer(serializers.ModelSerializer):
    destination = serializers.ChoiceField(
        choices=get_sharing_destination_options(include_download=False), required=True
    )
    target = TargetFilteredPrimaryKeyRelatedField(queryset=Target.objects.all(), required=True)
    share_existing_data = serializers.BooleanField(default=False, required=False, write_only=True)

    class Meta:
        model = PersistentShare
        fields = ('id', 'target', 'destination', 'user', 'created', 'share_existing_data')

    def create(self, validated_data):
        shared_existing_data = validated_data.pop('share_existing_data', None)
        if shared_existing_data:
            sharing_feedback = share_target_and_all_data(validated_data['destination'], validated_data['target'])
            if 'ERROR' in sharing_feedback.upper():
                raise serializers.ValidationError(
                    f"Failed to share existing data of target {validated_data['target'].name}: {sharing_feedback}"
                )

        return super().create(validated_data)
