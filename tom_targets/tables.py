import logging

import django_tables2 as tables

from tom_targets.models import Target

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TargetHTMXTable(tables.Table):
    class Meta:
        model = Target
        template_name = 'django_tables2/bootstrap.html'

        # TODO: switch to the template that overrides and adds htmx
        # template_name = 'tables/bootstrap_htmx.html'

        fields = ['id', 'name', 'ra', 'dec', ]
