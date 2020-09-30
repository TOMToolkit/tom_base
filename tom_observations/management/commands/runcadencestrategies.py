from django.core.management.base import BaseCommand

from tom_observations.cadence import get_cadence_strategy
from tom_observations.models import DynamicCadence


class Command(BaseCommand):
    help = 'Entry point for running cadence strategies.'

    def handle(self, *args, **kwargs):
        cadenced_groups = DynamicCadence.objects.filter(active=True)

        for cg in cadenced_groups:
            cadence_frequency = cg.cadence_parameters.get('cadence_frequency', -1)
            # TODO: pass cadence parameters in as kwargs or access them in the strategy
            # TODO: make cadence form strategy-specific
            strategy = get_cadence_strategy(cg.cadence_strategy)(cg, cadence_frequency)
            new_observations = strategy.run()
            if not new_observations:
                return 'No changes from cadence strategy.'
            else:
                return 'Cadence update completed, {0} new observations created.'.format(len(new_observations))
