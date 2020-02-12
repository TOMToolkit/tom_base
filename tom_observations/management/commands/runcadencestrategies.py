import json

from django.core.management.base import BaseCommand

from tom_observations.cadence import get_cadence_strategy
from tom_observations.models import ObservationGroup


class Command(BaseCommand):
    help = 'Entry point for running cadence strategies'

    # def add_arguments(self, parser):

    def handle(self, *args, **kwargs):
        cadenced_groups = ObservationGroup.objects.exclude(cadence_strategy='')

        for cg in cadenced_groups:
            cadence_frequency = json.loads(cg.cadence_parameters)['cadence_frequency']
            strategy = get_cadence_strategy(cg.cadence_strategy)(cg, cadence_frequency)
            new_observations = strategy.run()
            print(new_observations)
            if not new_observations:
                return 'Nothing for cadence to modify'
            else:
                return 'Cadence update completed, {0} new observations created.'.format(len(new_observations))
