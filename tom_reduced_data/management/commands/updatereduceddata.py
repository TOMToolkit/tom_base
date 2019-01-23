from requests.exceptions import HTTPError
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from tom_alerts import alerts
from tom_targets.models import Target


class Command(BaseCommand):
    help = 'Gets and updates time-series data for targets from the original source'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_id',
            help='Gets and updates time-series data for targets from the original source'
        )

    def handle(self, *args, **options):
        brokers = alerts.get_service_classes()
        target = None
        if options['target_id']:
            try:
                targets = [Target.objects.get(pk=options['target_id'])]
            except ObjectDoesNotExist:
                raise Exception('Invalid target id provided')
        else:
            targets = Target.objects.filter(source__in=brokers)

        failed_records = {}
        broker_classes = {}
        for broker in brokers:
            broker_classes[broker] = alerts.get_service_class(broker)
        for target in targets:
            try:
                broker_classes[target.source].process_reduced_data(target)
            except HTTPError:
                failed_records[target.source] = target.id

        if len(failed_records) == 0:
            return 'Update completed successfully'
        else:
            return 'Update completed with errors: {0}'.format(str(failed_records))
