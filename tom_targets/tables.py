import logging

import django_tables2 as tables
from django.db.models import Case, When
from django.utils.html import format_html
from django.urls import reverse

from tom_common.htmx_table import HTMXTable
from tom_targets.models import Target, TargetList

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TargetGroupTable(HTMXTable):
    # linkify makes the entry in the "name" column a link to the model detail page.
    name = tables.Column(
        linkify=True,
        attrs={"a": {"hx-boost": "false"}}
    )
    total_targets = tables.Column('Total Targets', orderable=True)
    id = tables.Column('Delete', orderable=False)

    def order_total_targets(self, queryset, is_descending):
        sorted_pks = [
            row.pk for row in sorted(
                queryset,
                key=lambda obj: obj.total_targets or "" or 0,
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

    def render_id(self, value):
        return format_html(f"""<a href="{reverse('targets:delete-group', kwargs={'pk': value})}" 
                    title="Delete Group" class="btn btn-danger">Delete</a>"""
                    )

    class Meta(HTMXTable.Meta):
        model = TargetList
        fields = ['selection', 'name', 'total_targets', 'created']


class TargetTable(HTMXTable):

    # Override selection column with Target-specific form binding
    selection = tables.CheckBoxColumn(
        accessor="pk",
        orderable=False,
        attrs={
            "input": {
                "name": "selected-target",
                "form": "grouping-form"
            },
            "th__input": {
                "class": "header-checkbox",
                "form": "grouping-form",
                "onclick": "event.stopPropagation();"
            }
        }
    )

    name = tables.Column(
        linkify=True,
        attrs={"a": {"hx-boost": "false"}}
    )

    class Meta(HTMXTable.Meta):
        model = Target
        fields = ['selection', 'name', 'type', 'ra', 'dec', ]

    # Override to use Target-specific partial
    partial_template_name = "tom_targets/partials/target_table_partial.html"
