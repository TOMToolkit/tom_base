import logging

from django import forms
from django.conf import settings
from django.db.models import Q

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Row, Column, HTML

import django_filters

from tom_common.htmx_table import HTMXTableFilterSet
from tom_targets.models import Target, TargetList
from tom_targets.utils import cone_search_filter

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


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


class TargetFilterSet(HTMXTableFilterSet):
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
                    # Column('name', css_class='form-group col-md-3'),
                ),
                # 2. The Toggle Button (HTML)
                HTML("""
                <div class="row">
                    <div class="col-md-12 mb-2">
                        <a class="btn btn-link p-0" data-toggle="collapse"
                           href="#advancedFilters"
                           role="button" aria-expanded="false" aria-controls="advancedFilters">Advanced &rsaquo;</a>
                    </div>
                </div>
                """),
                # 3. The Collapsible Container (Hidden by default)
                Div(
                    # Row 2: Filters
                    Row(
                        Column('type', css_class='form-group col-md-3'),
                        Column('targetlist__name', css_class='form-group col-md-3'),
                    ),
                    # Row 3: Cone Searches
                    Row(
                        Column('cone_search', css_class='form-group col-md-6'),
                        Column('target_cone_search', css_class='form-group col-md-6'),
                    ),
                    # Row 4: Dynamically added extra fields
                    Row(
                        *extra_columns,
                    ) if extra_columns else HTML(""),

                    # Bootstrap classes for functionality
                    css_class='collapse',
                    css_id='advancedFilters'  # must match the href in the "Advanced" HTML button above
                )
            )
        return self._form

    name = django_filters.CharFilter(method='filter_name', label='Name')

    # NOTE: this field is not displayed; the 'query' field is used instead
    def filter_name(self, queryset, name, value):
        """
        Return a queryset for targets with names or aliases containing the given coma-separated list of terms.
        """
        q_set = Q()
        for term in value.split(','):
            q_set |= Q(name__icontains=term) | Q(aliases__name__icontains=term)
        return queryset.filter(q_set).distinct()

    # NOTE: this field is not displayed; the 'query' field is used instead
    name_fuzzy = django_filters.CharFilter(method='filter_name_fuzzy', label='Name (Fuzzy)')

    def filter_name_fuzzy(self, queryset, name, value):
        """
        Return a queryset for targets with names or aliases fuzzy matching the given coma-separated list of terms.
        A fuzzy match is determined by the `make_simple_name` method of the `TargetMatchManager` class.
        """
        return Target.matches.match_fuzzy_name(value, queryset).distinct()

    cone_search = django_filters.CharFilter(
        method='filter_cone_search',
        label='Cone Search',
        help_text='RA, Dec, Search Radius (degrees)',
        widget=forms.TextInput(
            attrs={
                'placeholder': 'RA, Dec, Radius',
                'hx-get': "",
                'hx-trigger': "keyup[keyCode==13]",  # Trigger only on Enter key
                'hx-target': "div.table-container",
                'hx-swap': "innerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",
            }),
        )

    target_cone_search = django_filters.CharFilter(
        method='filter_cone_search',
        label='Cone Search (Target)',
        help_text='Target Name, Search Radius (degrees)',
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Target Name, Radius',
                'hx-get': "",
                'hx-trigger': "keyup[keyCode==13]",  # Trigger only on Enter key
                'hx-target': "div.table-container",
                'hx-swap': "innerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",
            }),
        )

    def filter_cone_search(self, queryset, name, value):
        """
        Perform a cone search filter on this filter's queryset,
        using the cone search utility method and either specified RA, DEC
        or the RA/DEC from the named target.

        This method prepares the arguments for tom_targets.utils.cone_search_filter.
        """
        if name == 'cone_search':
            ra, dec, radius = value.split(',')
        elif name == 'target_cone_search':
            target_name, radius = value.split(',')
            # try to get the ra, dec of the given Target
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
        label="Target Group",
        widget=forms.Select(  # override Select widget (even thought it's the default) to add htmx attributes
            attrs={
                'hx-get': "",  # triggered GET goes to the source URL by default
                'hx-trigger': "change",  # make the AJAX call when the selection changes
                'hx-target': "div.table-container",
                'hx-swap': "innerHTML",
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
                'hx-swap': "innerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",  # include the other filters in this FilterSet
            }
        )
    )

    def general_search(self, queryset, name, value):
        """
        Search targets by name.

        :param queryset: The current filtered queryset. By filtering on this queryset,
            we respect the filters that precede this method in the filter chain.
        :param name: The name of the filter field calling this method (e.g. 'query').
        :param value: The user's input from the General Search text field.
        """
        logger.debug(f'**** general_search -- value: {value}')

        if not value:
            return queryset  # early return

        return queryset.filter(Q(name__icontains=value))

    class Meta:
        model = Target
        fields = ['type', 'name', 'key', 'value', 'cone_search', 'targetlist__name']


class TargetGroupFilterSet(HTMXTableFilterSet):
    """
    This is a bare bones FilterSet for TargetGroups
    """

    class Meta:
        model = TargetList
        fields = []
