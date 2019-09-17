import django_filters
from django.db.models import Q

from tom_dataproducts.models import DataProduct


class DataProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label='Name', method='filter_name')
    facility = django_filters.CharFilter(field_name='observation_record__facility', label='Observation Record Facility')

    class Meta:
        model = DataProduct
        fields = ['name', 'facility']

    def filter_name(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(aliases__name__icontains=value))
