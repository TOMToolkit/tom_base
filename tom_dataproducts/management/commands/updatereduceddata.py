from requests.exceptions import HTTPError
import logging

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from tom_dataservices.dataservices import get_data_service_classes, get_data_service_class
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Gets and updates time-series data for a target with data extracted from data services. This will search ' \
        'existing data for sources that match installed data services and check those data services for new data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_id',
            help='ID of target for which you would like updated data. Leave blank to update all targets.'
        )

    def handle(self, *args, **options):
        dataservices = get_data_service_classes()
        dataservice_classes = {}
        for dataservice in dataservices:
            dataservice_classes[dataservice] = get_data_service_class(dataservice)()

        if options['target_id']:
            try:
                target = Target.objects.get(pk=options['target_id'])
                sources = [s.source_name for s in ReducedDatum.objects.filter(target=target).filter(
                    source_name__in=dataservice_classes.keys()).distinct()
                    ]
                targets = [target]
            except ObjectDoesNotExist:
                raise Exception('Invalid target id provided')
        else:
            sources = [s.source_name for s in ReducedDatum.objects.filter(
                source_name__in=dataservice_classes.keys()).distinct()
                ]
            targets = Target.objects.filter(
                id__in=ReducedDatum.objects.filter(
                    source_name__in=sources
                ).values_list('target').distinct())

        failed_records = {}
        for target in targets:
            for class_name, clazz in dataservice_classes.items():
                if class_name in sources:
                    logger.info(f"Updating {class_name} data for {target.name}")
                    try:
                        data_results = clazz.query_reduced_data(target)
                        clazz.to_reduced_datums(target, data_results)
                    except HTTPError:
                        failed_records[class_name] = target.id

        if len(failed_records) == 0:
            return 'Update completed successfully'
        else:
            return 'Update completed with errors: {0}'.format(str(failed_records))
