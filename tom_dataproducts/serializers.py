from django.conf import settings
from rest_framework import serializers

from tom_dataproducts.models import DataProductGroup, DataProduct, ReducedDatum
from tom_observations.models import ObservationRecord
from tom_observations.serializers import ObservationRecordFilteredPrimaryKeyRelatedField
from tom_targets.models import Target
from tom_targets.serializers import TargetFilteredPrimaryKeyRelatedField


class DataProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataProductGroup
        fields = ('name', 'created', 'modified')


# The ReducedDatumSerializer is not necessary until we implement the DataProductDetailAPIView and DataProductListAPIView
# class ReducedDatumSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ReducedDatum
#         fields = (
#             'data_product',
#             'data_type',
#             'source_name',
#             'source_location',
#             'timestamp',
#             'value'
#         )


class DataProductSerializer(serializers.ModelSerializer):
    target = TargetFilteredPrimaryKeyRelatedField(queryset=Target.objects.all())
    observation_record = ObservationRecordFilteredPrimaryKeyRelatedField(queryset=ObservationRecord.objects.all(),
                                                                         required=False)
    group = DataProductGroupSerializer(many=True, required=False)
    # reduced_datum_set = ReducedDatumSerializer(many=True, required=False)
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
            'group'
        )

        # TODO: use HyperlinkedModelSerializer
        #   for the HyperlinkedModelSerializer use something like this
        #   extra_kwargs = {
        #       "url": {
        #           "view_name": ":targets:detail",
        #           "lookup_field": "pk",
        #       }
        #   }

    def validate_data_product_type(self, value):
        for dp_type in settings.DATA_PRODUCT_TYPES.keys():
            if not value or value == dp_type:
                break
        else:
            raise serializers.ValidationError('Not a valid data_product_type. Valid data_product_types are {0}.'
                                              .format(', '.join(k for k in settings.DATA_PRODUCT_TYPES.keys())))
        return value
