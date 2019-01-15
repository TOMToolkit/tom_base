import django_filters
from django.db.models import Q

from tom_targets.models import Target


class TargetFilter(django_filters.FilterSet):
    key = django_filters.CharFilter(field_name='targetextra__key', label='Key')
    value = django_filters.CharFilter(field_name='targetextra__value', label='Value')
    identifier = django_filters.CharFilter(field_name='identifier', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='name', method='filter_name')

    def filter_name(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(name2__icontains=value) | Q(name3__icontains=value)
        )

    class Meta:
        model = Target
        fields = ['type', 'identifier', 'name', 'key', 'value']
