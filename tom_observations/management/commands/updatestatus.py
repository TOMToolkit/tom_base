from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist

from tom_targets.models import Target
from tom_observations.models import ObservationRecord
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
            failed_records[facility_name] = []
            clazz = facility.get_service_class(facility_name)
            qs = ObservationRecord.objects.filter(facility=facility_name)
            if target:
                qs = ObservationRecord.objects.filter(target=target)
            records_for_facility = ObservationRecord.objects.exclude(status__in=clazz.get_terminal_observing_states())
            for record in records_for_facility:
                try:
                    clazz.update_observing_status(record.observation_id)
                except Exception as e:
                    failed_records[facility_name].append((record.observation_id, str(e)))
        success = True
        for facility_name, errors in failed_records.items():
            if len(errors) > 0:
                success = False
                break
        if success:
            return "Update completed successfully"
        else:
            return 'Update completed with errors: {0}'.format(str(failed_records))
