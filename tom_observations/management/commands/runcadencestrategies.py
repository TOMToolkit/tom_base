from django.core.management.base import BaseCommand

from tom_observations.cadence import get_cadence_strategy
from tom_observations.models import DynamicCadence


class Command(BaseCommand):
    """
    This management command ensures that all cadences are kept up to date. It is intended to be run
    by a cron job, and the frequency should be whatever is determined to be the desired frequency
    by the PI.
    """

    help = 'Entry point for running cadence strategies.'

    def handle(self, *args, **kwargs):
        cadenced_groups = DynamicCadence.objects.filter(active=True)

        for cg in cadenced_groups:
            strategy = get_cadence_strategy(cg.cadence_strategy)(cg)
            new_observations = strategy.run()
            if not new_observations:
                return 'No changes from cadence strategy.'
            else:
                return 'Cadence update completed, {0} new observations created.'.format(len(new_observations))
