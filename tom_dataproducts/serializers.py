from rest_framework import serializers
from .models import DataProductGroup, DataProduct, ReducedDatum


class DataProductGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DataProductGroup
        fields = ('name', 'created', 'modified')


class DataProductSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DataProduct
        fields = (
            'product_id',
            'target',
            'observation_record',
            'data',
            'extra_data',
            'group',
            'created',
            'modified',
            'data_product_type',
            'featured',
            'thumbnail'
        )


class ReducedDatumSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ReducedDatum
        fields = (
            'target',
            'data_product',
            'data_type',
            'source_name',
            'source_location',
            'timestamp',
            'value'
        )
