import django_filters
from django.db.models import Q
from django.conf import settings

from tom_targets.models import Target


def filter_type_for_field(field_type):
    if field_type == 'number':
        return django_filters.RangeFilter
    else:
        return django_filters.CharFilter


class TargetFilter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in settings.EXTRA_FIELDS:
            filter_type = filter_type_for_field(field['type'])
            new_filter = filter_type(field_name=field['name'], method='filter_extra')
            new_filter.parent = self
            self.filters[field['name']] = new_filter

    identifier = django_filters.CharFilter(field_name='identifier', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='name', method='filter_name')

    def filter_name(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(name2__icontains=value) | Q(name3__icontains=value)
        )

    def filter_extra(self, queryset, name, value):
        queryset = queryset.filter(targetextra__key=name)
        if isinstance(value, slice):
            return queryset.filter(targetextra__value__gte=value.start, targetextra__value__lte=value.stop)
        else:
            return queryset.filter(targetextra__value__icontains=value)

    class Meta:
        model = Target
        fields = ['type', 'identifier', 'name']
