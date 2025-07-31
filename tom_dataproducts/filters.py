import django_filters
from django.db.models import Q

from tom_dataproducts.models import DataProduct, ReducedDatum


class DataProductFilter(django_filters.rest_framework.FilterSet):
    target_name = django_filters.CharFilter(label='Target Name', method='filter_name')
    facility = django_filters.CharFilter(field_name='observation_record__facility', label='Observation Record Facility')

    class Meta:
        model = DataProduct
        fields = ['target_name', 'facility']

    def filter_name(self, queryset, name, value):
        return queryset.filter(Q(target__name__icontains=value) | Q(target__aliases__name__icontains=value))


class ReducedDatumFilter(django_filters.rest_framework.FilterSet):
    target_name = django_filters.CharFilter(label='Target Name', method='filter_name')
    data_product_pk = django_filters.NumberFilter(field_name='data_product__pk', label='Data Product Primary Key')
    data_product_product_id = django_filters.CharFilter(field_name='data_product__product_id',
                                                        label='Data Product "Product ID" or filename')

    class Meta:
        model = ReducedDatum
        fields = ['target__id', 'target_name', 'data_product_pk', 'source_name', 'data_type']

    def filter_name(self, queryset, name, value):
        return queryset.filter(Q(target__name__icontains=value) | Q(target__aliases__name__icontains=value))
