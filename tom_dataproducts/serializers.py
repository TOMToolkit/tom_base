from rest_framework import serializers
from .models import DataProductGroup, DataProduct, ReducedDatum


class DataProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataProductGroup
        fields = ('name', 'created', 'modified')


class DataProductSerializer(serializers.ModelSerializer):
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

        # TODO: use HyperlinkedModelSerializer
        #   for the HyperlinkedModelSerializer use something like this
        #   extra_kwargs = {
        #       "url": {
        #           "view_name": ":targets:detail",
        #           "lookup_field": "pk",
        #       }
        #   }


class ReducedDatumSerializer(serializers.ModelSerializer):
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
