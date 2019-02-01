from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from tom_targets.models import Target
from tom_observations import facility


class Command(BaseCommand):
    help = 'Updates the status of each observation requests in the TOM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_id',
            help='Update observation statuses for a single target'
        )

    def handle(self, *args, **options):
        target = None
        if options['target_id']:
            try:
                target = Target.objects.get(pk=options['target_id'])
            except ObjectDoesNotExist:
                raise Exception('Invalid target id provided')

        failed_records = {}
        for facility_name in facility.get_service_classes():
            clazz = facility.get_service_class(facility_name)
            failed_records[facility_name] = clazz().update_all_observation_statuses(target=target)
        success = True
        for facility_name, errors in failed_records.items():
            if len(errors) > 0:
                success = False
                break
        if success:
            return 'Update completed successfully'
        else:
            return 'Update completed with errors: {0}'.format(str(failed_records))
