import django_filters
from django.db.models import Q

from tom_dataproducts.models import DataProduct, ReducedDatum


class DataProductFilter(django_filters.rest_framework.FilterSet):
    """
    Filters are available for DataProduct objects:
        - target_name: Filter by target name or alias.
        - facility: Filter by the facility of the observation record associated with the data product.

    Access these filters via the API endpoint:
        `GET /api/dataproducts/?target_name=<name>&facility=<facility>`
    """
    target_name = django_filters.CharFilter(label='Target Name', method='filter_name')
    facility = django_filters.CharFilter(field_name='observation_record__facility', label='Observation Record Facility')

    class Meta:
        model = DataProduct
        fields = ['target_name', 'facility']

    def filter_name(self, queryset, name, value):
        return queryset.filter(Q(target__name__icontains=value) | Q(target__aliases__name__icontains=value))


class ReducedDatumFilter(django_filters.rest_framework.FilterSet):
    """
    Filters are available for ReducedDatum objects:
        - target__id: Filter by target ID.
        - target_name: Filter by target name or alias.
        - data_product_pk: Filter by the primary key of the associated DataProduct.
        - data_product_product_id: Filter by the "Product ID" or filename of the associated DataProduct.
        - source_name: Filter by the name of the source.
        - data_type: Filter by the type of data (e.g., 'photometry', 'spectrum').

    Access these filters via the API endpoint:
        `GET /api/reduceddatums/?target__id=<id>&data_type=<type>`
    """
    target_name = django_filters.CharFilter(label='Target Name', method='filter_name')
    data_product_name = django_filters.CharFilter(method='filter_data_product_name', label='Data Product filename')

    class Meta:
        model = ReducedDatum
        fields = ['target__id', 'target_name', 'data_product__id', 'source_name', 'data_type']

    def filter_name(self, queryset, name, value):
        return queryset.filter(Q(target__name__icontains=value) | Q(target__aliases__name__icontains=value))

    def filter_data_product_name(self, queryset, name, value):
        return queryset.filter(data_product__product_id__icontains=value) | \
               queryset.filter(data_product__data__icontains=value)
