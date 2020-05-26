import json

from django.core.management.base import BaseCommand

from tom_observations.cadence import get_cadence_strategy
from tom_observations.models import ObservationGroup


class Command(BaseCommand):
    help = 'Entry point for running cadence strategies.'

    def handle(self, *args, **kwargs):
        cadenced_groups = ObservationGroup.objects.exclude(cadence_strategy='')

        for cg in cadenced_groups:
            cadence_frequency = json.loads(cg.cadence_parameters)['cadence_frequency']
            strategy = get_cadence_strategy(cg.cadence_strategy)(cg, cadence_frequency)
            new_observations = strategy.run()
            if not new_observations:
                return 'No changes from cadence strategy.'
            else:
                return 'Cadence update completed, {0} new observations created.'.format(len(new_observations))
