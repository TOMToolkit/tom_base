import logging

import django_filters
import django_tables2 as tables
from django import forms
from django.db.models import Q, Case, When
from django.conf import settings
from django.utils.module_loading import import_string
from django_tables2 import SingleTableMixin
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Row, Column, HTML


logger = logging.getLogger(__name__)

htmx_attributes = {'hx-get': "",
                   'hx-trigger': "change",
                   'hx-target': "div.table-container",
                   'hx-swap': "innerHTML",
                   'hx-indicator': ".progress",
                   'hx-include': "closest form",
                   }

htmx_attributes_instant = {**htmx_attributes, 'hx-trigger': "change"}

htmx_attributes_onenter = {**htmx_attributes, 'hx-trigger': "keyup[keyCode==13]"}

htmx_attributes_delayed = {**htmx_attributes, 'hx-trigger': "input changed delay:200ms", 'hx-sync': 'this:replace'}


class HTMXTable(tables.Table):
    """
    Base Table class for HTMX-driven interactive tables.

    Provides:
    - Default HTMX attributes for sorting, pagination, and filter preservation
    - CheckBoxColumn for row selection (include 'selection' in Meta.fields to enable)
    - Shared bootstrap_htmx.html template
    - Default partial template with override point

    Subclasses should:
    1. Set ``Meta.model`` and ``Meta.fields``
    2. Inherit Meta via ``class Meta(HTMXTable.Meta):``
    3. Optionally override ``partial_template_name`` for a model-specific partial
    """

    selection = tables.CheckBoxColumn(
        accessor="pk",
        orderable=False,
        attrs={
            "input": {"name": "selected-row",
                      "form": "grouping-form"},
            "th__input": {
                "class": "header-checkbox",
                "form": "grouping-form",
                "onclick": "event.stopPropagation();"
            }
        }
    )

    def model_property_ordering(self,queryset, is_descending, property=None):
        sorted_pks = [
            row.pk for row in sorted(
                queryset,
                key=lambda obj: obj.__getattribute__(property) or "" or 0,
                reverse=is_descending,
            )
        ]

        # Use Case/When to preserve the Python-sorted order in the queryset
        # map the sorted PKs to the position in the enumeration
        preserved_order = Case(*[When(pk=pk, then=position) for position, pk in enumerate(sorted_pks)])

        # re-order the queryset by the python-sorted (the .filter is just for validation)
        sorted_queryset = queryset.filter(pk__in=sorted_pks).order_by(preserved_order)
        is_sorted = True

        return (sorted_queryset, is_sorted)

    class Meta:
        template_name = 'tom_common/bootstrap_htmx.html'
        attrs = {
            "class": "table table-striped table-hover table-sm",
            "hx-include": "#filter-form",
            "hx-target": "div.table-container",
            "hx-swap": "innerHTML",
            "hx-boost": "true",
        }

    # Default partial template -- override via class attribute or get_partial_template_name()
    partial_template_name = "tom_common/partials/htmx_table_partial.html"

    def get_partial_template_name(self) -> str:
        """Return path to the partial template for HTMX responses."""
        return self.partial_template_name


class HTMXTableFilterSet(django_filters.rest_framework.FilterSet):
    """
    Base FilterSet for HTMX-enabled tables with customizable General Search.

    Provides:
    - A 'query' CharFilter with HTMX attributes (debounced input)
    - A default general_search() method
    - A get_general_search_function() override point for customization
    - Settings-based search function override via GENERAL_SEARCH_FUNCTIONS

    Customization options (in order of simplicity):
    1. Override general_search() in your FilterSet subclass
    2. Add a dotted path in settings.GENERAL_SEARCH_FUNCTIONS
    3. Override get_general_search_function() for full control

    Subclasses should:
    1. Add the Model and relevant fields to the Meta
    2. Define their own general_search() or override get_general_search_function()
    2. Add model-specific filters with HTMX widget attrs
    3. Override the form property to configure crispy-forms layout
    """

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

            advanced_field_names = [f for f in self.Meta.fields]
            advanced_columns = [Column(name, css_class='form-group col-md-3') for name in advanced_field_names]

            # Define the structure using Bootstrap Grid (Row/Column)
            self._form.helper.layout = Layout(
                # Row 1: Primary Search parameters
                Div(
                    Column('query', css_class='form-group col-md-3'),
                ),
                # 2. The Toggle Button (HTML)
                Div(
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
                            *advanced_columns,
                        ),

                        # Bootstrap classes for functionality
                        css_class='collapse',
                        css_id='advancedFilters'  # must match the href in the "Advanced" HTML button above
                    )
                ) if advanced_columns else HTML("")
            )
        return self._form

    query = django_filters.CharFilter(
        method='_dispatch_general_search',
        label="General search",
        widget=forms.TextInput(attrs={
            'hx-get': "",
            'hx-trigger': "input changed delay:200ms",
            'hx-sync': 'this:replace',
            'hx-target': "div.table-container",
            'hx-swap': "innerHTML",
            'hx-indicator': ".progress",
            'hx-include': "closest form",
        })
    )

    def _dispatch_general_search(self, queryset, name, value):
        """Internal dispatcher -- calls the user-overridable search function."""
        search_func = self.get_general_search_function()
        return search_func(queryset, name, value)

    def get_general_search_function(self):
        """
        Return the callable used for general search.

        Checks ``settings.GENERAL_SEARCH_FUNCTIONS`` first for a dotted path
        keyed by ``'app_label.ModelName'``, then falls back to
        ``self.general_search``.

        Developers can register a standalone function in settings.py without
        subclassing anything::

            # settings.py
            GENERAL_SEARCH_FUNCTIONS = {
                'tom_targets.Target': 'custom_code.search.my_target_search',
            }

        Returns:
            callable: A function with signature (queryset, name, value) -> QuerySet
        """
        search_map = getattr(settings, 'GENERAL_SEARCH_FUNCTIONS', {})
        model_label = f'{self.Meta.model._meta.app_label}.{self.Meta.model.__name__}'
        func_path = search_map.get(model_label)
        if func_path:
            return import_string(func_path)
        return self.general_search

    def general_search(self, queryset, name, value):
        """
        Default general search implementation. This Searches all model fields for the value.
        If ANY field shows the value, it will be displayed.
        NOTE: This search is not limited to displayed fields and does not include non-field columns.

        Concrete subclasses that don't wish to use this default function should either:
        - Override this method directly, or
        - Override get_general_search_function() to return a different callable

        :param queryset: The current filtered queryset. By filtering on this queryset,
            we respect the filters that precede this method in the filter chain.
        :param name: The name of the filter field calling this method (e.g. 'query').
        :param value: The user's input from the General Search text field.
        :returns: A filtered QuerySet.
        """
        if not value:
            return queryset
        logger.debug(f'**** general_search -- value: {value}')

        query = Q()
        for field in self.Meta.model._meta.get_fields():
            if not (field.many_to_many or field.many_to_one):  # We need to remove FK relationships
                query |= Q(**{f'{field.name}__icontains': value})
        return queryset.filter(query)


    class Meta:
        abstract = True


class HTMXTableViewMixin(SingleTableMixin):
    """
    Mixin for views that serve HTMX-driven tables.

    Extends ``django_tables2.SingleTableMixin`` so that views only need
    to inherit from ``HTMXTableViewMixin`` (not both this and
    ``SingleTableMixin``).

    Automatically returns the partial template for HTMX requests
    and the full page template for normal requests.

    Requires:
    - ``table_class``: set to an HTMXTable subclass
    - ``template_name``: the full-page template (set as usual)

    Provides:
    - ``record_count``: total number of records (from paginator)
    - ``empty_database``: whether the model table has any records at all
    """

    def get_template_names(self) -> list[str]:
        if self.request.htmx:
            return [self.table_class(data=[]).get_partial_template_name()]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['record_count'] = context['paginator'].count
        context['empty_database'] = not self.model.objects.exists()
        return context
