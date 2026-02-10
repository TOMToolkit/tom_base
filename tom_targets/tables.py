import logging

import django_tables2 as tables

from tom_common.htmx_table import HTMXTable
from tom_targets.models import Target

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
