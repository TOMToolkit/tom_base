import django_filters
from django.db.models import Q
from django.conf import settings

from tom_targets.models import Target


def filter_for_field(field):
    if field['type'] == 'number':
        return django_filters.RangeFilter(field_name=field['name'], method=filter_number)
    elif field['type'] == 'boolean':
        return django_filters.BooleanFilter(field_name=field['name'], method=filter_boolean)
    elif field['type'] == 'datetime':
        return django_filters.DateTimeFromToRangeFilter(field_name=field['name'], method=filter_datetime)
    elif field['type'] == 'string':
        return django_filters.CharFilter(field_name=field['name'], method=filter_text)
    else:
        raise ValueError(
            'Invalid field type {}. Field type must be one of: number, boolean, datetime string'.format(field['type'])
        )


def filter_number(queryset, name, value):
    return queryset.filter(
        targetextra__key=name, targetextra__float_value__gte=value.start, targetextra__float_value__lte=value.stop
    )


def filter_datetime(queryset, name, value):
    return queryset.filter(
        targetextra__key=name, targetextra__time_value__gte=value.start, targetextra__time_value__lte=value.stop
    )


def filter_boolean(queryset, name, value):
    return queryset.filter(targetextra__key=name, targetextra__bool_value=value)


def filter_text(queryset, name, value):
    return queryset.filter(targetextra__key=name, targetextra__value__icontains=value)


class TargetFilter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in settings.EXTRA_FIELDS:
            new_filter = filter_for_field(field)
            new_filter.parent = self
            self.filters[field['name']] = new_filter

    identifier = django_filters.CharFilter(field_name='identifier', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='name', method='filter_name')

    def filter_name(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(name2__icontains=value) | Q(name3__icontains=value)
        )

    class Meta:
        model = Target
        fields = ['type', 'identifier', 'name']
