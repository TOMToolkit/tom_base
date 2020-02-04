from django.core.management.base import BaseCommand

from tom_observations.models import ObservationGroup


class Command(BaseCommand):
    help = 'Entry point for running cadence strategies'

    # def add_arguments(self, parser):

    def handle(self, *args, **kwargs):
        cadenced_groups = ObservationGroup.objects.exclude(cadence_strategy='')

        for cg in cadenced_groups:
            strategy = get_cadence_strategy(cg.cadence_strategy)()
            strategy.run()
