import django_filters

from tom_targets.models import Target


class TargetFilter(django_filters.FilterSet):
    key = django_filters.CharFilter(field_name='targetextra__key', label='Key')
    value = django_filters.CharFilter(field_name='targetextra__value', label='Value')
    identifier = django_filters.CharFilter(field_name='identifier', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Target
        fields = ['type', 'identifier', 'name', 'key', 'value']
