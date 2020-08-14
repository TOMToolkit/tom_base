from math import radians

from django.conf import settings
from django.db.models import ExpressionWrapper, FloatField, Q
from django.db.models.functions.math import ACos, Cos, Radians, Pi, Sin
import django_filters

from tom_targets.models import Target, TargetList


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
    key = django_filters.CharFilter(field_name='targetextra__key', label='Key')
    value = django_filters.CharFilter(field_name='targetextra__value', label='Value')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in settings.EXTRA_FIELDS:
            new_filter = filter_for_field(field)
            new_filter.parent = self
            self.filters[field['name']] = new_filter

    name = django_filters.CharFilter(method='filter_name', label='Name')

    def filter_name(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(aliases__name__icontains=value)).distinct()

    cone_search = django_filters.CharFilter(method='filter_cone_search', label='Cone Search',
                                            help_text='RA, Dec, Search Radius (degrees)')

    target_cone_search = django_filters.CharFilter(method='filter_cone_search', label='Cone Search (Target)',
                                                   help_text='Target Name, Search Radius (degrees)')

    def filter_cone_search(self, queryset, name, value):
        """
        Executes cone search by annotating each target with separation distance from either the specified RA/Dec or
        the RA/Dec of the specified target. Formula is from Wikipedia: https://en.wikipedia.org/wiki/Angular_distance
        The result is converted to radians.

        Cone search is preceded by a square search to reduce the search radius before annotating the queryset, in
        order to make the query faster.
        """
        if name == 'cone_search':
            ra, dec, radius = value.split(',')
        elif name == 'target_cone_search':
            target_name, radius = value.split(',')
            targets = Target.objects.filter(
                Q(name__icontains=target_name) | Q(aliases__name__icontains=target_name)
            ).distinct()
            if len(targets) == 1:
                ra = targets[0].ra
                dec = targets[0].dec
            else:
                return queryset.filter(name=None)

        ra = float(ra)
        dec = float(dec)

        double_radius = float(radius) * 2
        queryset = queryset.filter(ra__gte=ra - double_radius, ra__lte=ra + double_radius,
                                   dec__gte=dec - double_radius, dec__lte=dec + double_radius)

        separation = ExpressionWrapper(
            180 * ACos(
                (Sin(radians(dec)) * Sin(Radians('dec'))) +
                (Cos(radians(dec)) * Cos(Radians('dec')) * Cos(radians(ra) - Radians('ra')))
            ) / Pi(), FloatField()
        )

        return queryset.annotate(separation=separation).filter(separation__lte=radius)

    # hide target grouping list if user not logged in
    def get_target_list_queryset(request):
        if request.user.is_authenticated:
            return TargetList.objects.all()
        else:
            return TargetList.objects.none()

    targetlist__name = django_filters.ModelChoiceFilter(queryset=get_target_list_queryset, label="Target Grouping")

    class Meta:
        model = Target
        fields = ['type', 'name', 'key', 'value', 'cone_search', 'targetlist__name']
