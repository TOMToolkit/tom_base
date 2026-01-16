import logging

from django import forms
from django.conf import settings
from django.db.models import Q

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div, HTML

import django_filters

from tom_targets.models import Target, TargetList
from tom_targets.utils import cone_search_filter

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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


class TargetFilterSet(django_filters.rest_framework.FilterSet):
    """
    Filters are available for Target objects:
        - type: Filter by target type (e.g., 'SIDEREAL', 'NON_SIDEREAL').
        - name: Filter by target name or alias.
        - key: Filter by a specific key in the target's extra fields.
        - value: Filter by a specific value in the target's extra fields.
        - cone_search: Perform a cone search around a given position (RA,Dec,Radius).
        - targetlist__name: Filter by the name of the target list the target belongs to.
        - name_fuzzy: Perform a fuzzy search on the target name or aliases.
        - target_cone_search: Perform a cone search on the target's position (radius).
        - order: Order the results by a specific field ('name', 'created', 'modified')

    Access these filters via the API endpoint:
        `GET /api/targets/?type=<type>&cone_search=<ra,dec,radius>`
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in settings.EXTRA_FIELDS:
            new_filter = filter_for_field(field)
            new_filter.parent = self
            self.filters[field['name']] = new_filter


    @property
    def form(self):
        """Override form property to configure crispy forms helper. This is to remove
        the Submit button which is not needed because HTMX is making AJAX requests.

        Also, add the FormHelper.Layout definition
        """
        if not hasattr(self, '_form'):
            self._form = super().form
            # Configure crispy forms helper - no submit button, no form tag
            self._form.helper = FormHelper()
            self._form.helper.form_tag = False  # Don't render <form> tags (template handles it)
            self._form.helper.disable_csrf = True  # Template handles CSRF if needed
            self._form.helper.form_show_labels = True  # Explicitly clear any inputs/buttons

            # Prepare extra fields for the layout
            extra_field_names = [f['name'] for f in settings.EXTRA_FIELDS]
            extra_columns = [Column(name, css_class='form-group col-md-3') for name in extra_field_names]

            # Define the structure using Bootstrap Grid (Row/Column)
            self._form.helper.layout = Layout(
                # Row 1: Primary Search parameters
                Row(
                    Column('query', css_class='form-group col-md-3'),
                    Column('name', css_class='form-group col-md-3'),
                    Column('type', css_class='form-group col-md-3'),
                    Column('targetlist__name', css_class='form-group col-md-3'),
                ),
                # Row 2: Location and Coordinates
                Row(
                    Column('cone_search', css_class='form-group col-md-6'),
                    Column('target_cone_search', css_class='form-group col-md-6'),
                ),
                # Row 3: Key/Value and Fuzzy search
                Row(
                    Column('key', css_class='form-group col-md-3'),
                    Column('value', css_class='form-group col-md-3'),
                    Column('name_fuzzy', css_class='form-group col-md-3'),
                ),
                # Row 4: Dynamically added extra fields
                Row(
                    *extra_columns,
                ) if extra_columns else HTML("")
            )
        return self._form


    name = django_filters.CharFilter(method='filter_name', label='Name')

    def filter_name(self, queryset, name, value):
        """
        Return a queryset for targets with names or aliases containing the given coma-separated list of terms.
        """
        q_set = Q()
        for term in value.split(','):
            q_set |= Q(name__icontains=term) | Q(aliases__name__icontains=term)
        return queryset.filter(q_set).distinct()

    name_fuzzy = django_filters.CharFilter(method='filter_name_fuzzy', label='Name (Fuzzy)')

    def filter_name_fuzzy(self, queryset, name, value):
        """
        Return a queryset for targets with names or aliases fuzzy matching the given coma-separated list of terms.
        A fuzzy match is determined by the `make_simple_name` method of the `TargetMatchManager` class.
        """
        return Target.matches.match_fuzzy_name(value, queryset).distinct()

    cone_search = django_filters.CharFilter(method='filter_cone_search', label='Cone Search',
                                            help_text='RA, Dec, Search Radius (degrees)')

    target_cone_search = django_filters.CharFilter(method='filter_cone_search', label='Cone Search (Target)',
                                                   help_text='Target Name, Search Radius (degrees)')

    def filter_cone_search(self, queryset, name, value):
        """
        Perform a cone search filter on this filter's queryset,
        using the cone search utlity method and either specified RA, DEC
        or the RA/DEC from the named target.
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
        else:
            return queryset

        ra = float(ra)
        dec = float(dec)

        return cone_search_filter(queryset, ra, dec, radius)

    key = django_filters.CharFilter(field_name='targetextra__key', label='Key')
    value = django_filters.CharFilter(field_name='targetextra__value', label='Value')

    # hide target grouping list if user not logged in
    def get_target_list_queryset(request):
        if request.user.is_authenticated:
            return TargetList.objects.all()
        else:
            return TargetList.objects.none()

    targetlist__name = django_filters.ModelChoiceFilter(
        queryset=get_target_list_queryset,
        label="Target Grouping",
        widget=forms.Select(  # override Select widget (even thought it's the default) to add htmx attributes
            attrs={
                'hx-get': "",  # triggered GET goes to the source URL by default
                'hx-trigger': "change",  # make the AJAX call when the selection changes
                'hx-target': "div.table-container",
                'hx-swap': "outerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",  # include the other filters in this FilterSet
            }
        )
    )

    # Here, we override the default 'type' ChoiceFilter so we can add htmx attributes to it's widget
    type = django_filters.ChoiceFilter(
        choices=Target.TARGET_TYPES,
        widget=forms.Select(
            attrs={
                'hx-get': "",  # triggered GET goes to the source URL by default
                'hx-trigger': "change",  # make the AJAX call when the selection changes
                'hx-target': "div.table-container",
                'hx-swap': "outerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",  # include the other filters in this FilterSet
            }
        )
    )

    # Set up a search box that filters the Targets
    query = django_filters.CharFilter(
        # TODO: make this customizable like TargetFilterSet.get_universal_search_callable
        method='universal_search',
        label="General search",
        # override widget in order to add htmx attributes
        widget=forms.TextInput(
            attrs={
                'hx-get': "",  # triggered GET goes to the source URL by default
                'hx-trigger': "input delay:200ms",  # AJAX call when input changes (delayed to debounce)
                'hx-target': "div.table-container",
                'hx-swap': "outerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",  # include the other filters in this FilterSet
            }
        ))

    # TODO: this method should be customizable and it needs a lot of work atm.
    def universal_search(self, queryset, name, value):
        """

        :param queryset: this is the result of the previous filters. By returning
            queryset.fitler(new_Q), we are respecting the filters that preceed this method
            the filter chain.
        :param name: the Filter calling here (the query CharFilter above, for example)
        :param value: what the user has typed in the query CharField so far
        """
        if not value:
            return queryset  # early return

        from decimal import Decimal
        # if a digit is being entered, query the RA, and DEC fields
        if value.replace(".", "", 1).isdigit():
            value = Decimal(value)
            logger.debug(f'**** universal_search --  decoded digit value: {value}')
            return queryset.filter(Q(ra__icontains=value) | Q(dec__icontains=value))

        return queryset.filter(Q(name__icontains=value))

    class Meta:
        model = Target
        fields = ['type', 'name', 'key', 'value', 'cone_search', 'targetlist__name']
