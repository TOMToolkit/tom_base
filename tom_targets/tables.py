import logging

import django_tables2 as tables

from tom_targets.models import Target

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TargetHTMXTable(tables.Table):

    selection = tables.CheckBoxColumn(
        accessor="pk",
        orderable=False,
        # these attrs of the CheckBoxColumn bind the input to the grouping-form
        attrs={
            "input": {
                "name": "selected-target",  # Match the name expected by TOM views
                "form": "grouping-form"     # Bind to the form id defined in target_list.html
            },
            "th__input": {
                "class": "header-checkbox",  # Optional class for JS targeting
                "form": "grouping-form",
                # this prevents the click from bubbling up to the sorting header
                "onclick": "event.stopPropagation();"
            }
        }
    )

    name = tables.Column(linkify=True)

    class Meta:
        model = Target
        # this is the default template from django_tables2 (it does not have HTMX attributes)
        # template_name = 'django_tables2/bootstrap.html'

        # this template extends the bootstrap.html template with HTMX attributes.
        template_name = 'tom_targets/bootstrap_htmx.html'

        fields = ['selection', 'id', 'name', 'type', 'ra', 'dec', ]

    def get_partial_template_name(self) -> str:
        """
        Return the name partial that renders the table (probabaly via
        django_tables2.render_table). The purpose of this methods is
        so a TOM developer can override this method to supply a custom
        partial

        The partial itself can be as simple as:
        ```html
        {% load render_table from django_tables2 %}
        {% render_table table %}
        ```
        """
        partial_template_name = "tom_targets/target_table_partial.html"
        return partial_template_name
