from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist

from tom_observations.models import ObservationRecord
from tom_observations import facility


class Command(BaseCommand):
    help = 'Updates the status of each observation requests in the TOM'

    def handle(self, *args, **options):
        for facility_class in facility.get_service_classes():
            clazz = facility.get_service_class(facility_class)
            requests = clazz.get_observation_status()
            for observing_request in requests:
                try:
                    record = ObservationRecord.objects.get(observation_id=observing_request[0])
                    record.status = observing_request[1]
                    record.save()
                except ObjectDoesNotExist:
                    pass