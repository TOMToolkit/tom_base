from django.core.management.base import BaseCommand
from tom_observations import facility
from tom_observations.models import ObservationRecord


class Command(BaseCommand):
    help = 'Downloads data for all completed observations'

    def handle(self, *args, **options):
        facility_classes = {}
        for facility_name in facility.get_service_classes():
            facility_classes[facility_name] = facility.get_service_class(facility_name)()
        observation_records = ObservationRecord.objects.all()
        for record in observation_records:
            if record.status not in facility_classes[record.facility].get_terminal_observing_states():
                facility_classes[record.facility].update_observation_status(record.observation_id)
                facility_classes[record.facility].save_data_products(record)

        return 'completed command'
