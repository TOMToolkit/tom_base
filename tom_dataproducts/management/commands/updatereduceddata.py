from requests.exceptions import HTTPError
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from tom_alerts import alerts
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum


class Command(BaseCommand):
    help = 'Gets and updates time-series data for alert-generated targets from the original alert source.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_id',
        )

    def handle(self, *args, **options):
        brokers = alerts.get_service_classes()
        broker_classes = {}
        for broker in brokers:
            broker_classes[broker] = alerts.get_service_class(broker)()

        target = None
        sources = [s.source_name for s in ReducedDatum.objects.filter(source_name__in=broker_classes.keys()).distinct()]
        if options['target_id']:
            try:
                targets = [Target.objects.get(pk=options['target_id'])]
            except ObjectDoesNotExist:
                raise Exception('Invalid target id provided')
        else:
            targets = Target.objects.filter(
                id__in=ReducedDatum.objects.filter(
                    source_name__in=sources
                ).values_list('target').distinct())

        failed_records = {}
        for target in targets:
            for class_name, clazz in broker_classes.items():
                if class_name in sources:
                    try:
                        clazz.process_reduced_data(target)
                    except HTTPError:
                        failed_records[class_name] = target.id

        if len(failed_records) == 0:
            return 'Update completed successfully'
        else:
            return 'Update completed with errors: {0}'.format(str(failed_records))
