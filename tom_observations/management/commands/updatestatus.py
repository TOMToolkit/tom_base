from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist

from tom_observations.models import ObservationRecord
from tom_observations import facility


class Command(BaseCommand):
    help = 'Updates the status of each observation requests in the TOM'

    def handle(self, *args, **options):
        failed_records = {}
        for facility_name in facility.get_service_classes():
            failed_records[facility_name] = []
            clazz = facility.get_service_class(facility_name)
            records_for_facility = ObservationRecord.objects.filter(facility=facility_name).exclude(status__in=clazz.get_terminal_observing_states())
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
            print("Update completed successfully")
        else:
            print('Update completed with errors: ')
            print(failed_records)
