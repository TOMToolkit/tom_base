import logging
import traceback

from django.core.management.base import BaseCommand

from tom_observations.cadence import get_cadence_strategy
from tom_observations.models import DynamicCadence


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    This management command ensures that all cadences are kept up to date. It is intended to be run
    by a cron job, and the frequency should be whatever is determined to be the desired frequency
    by the PI.
    """

    help = 'Entry point for running cadence strategies.'

    def handle(self, *args, **kwargs):
        cadenced_groups = DynamicCadence.objects.filter(active=True)

        updated_cadences = []

        for cg in cadenced_groups:
            try:
                strategy = get_cadence_strategy(cg.cadence_strategy)(cg)
                try:
                    new_observations = strategy.run()
                except Exception as e:
                    logger.error((f'Unable to run cadence_group: {cg}; strategy {strategy};'
                                  f' with id {cg.id} due to error: {e}'))
                    logger.error(f'{traceback.format_exc()}')
                    continue
                if not new_observations:
                    logger.log(msg=f'No changes from dynamic cadence {cg}', level=logging.INFO)
                else:
                    logger.log(msg=f'''Cadence update completed for dynamic cadence {cg},
                                       {len(new_observations)} new observations created.''',
                               level=logging.INFO)
                    updated_cadences.append(cg.observation_group)
            except Exception as e:
                logger.error(msg=f'Unable to run strategy {cg} with id {cg.id} due to error: {e}')

        if updated_cadences:
            msg = 'Created new observations for dynamic cadences with observation groups: {0}.'
            return msg.format(', '.join([str(cg) for cg in updated_cadences]))
        else:
            return 'No new observations for any dynamic cadences.'
