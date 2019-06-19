from django.core.management.base import BaseCommand

from tom_alerts.alerts import get_service_class


class Command(BaseCommand):
    help = 'Listen to an antares stream and save targets'

    def add_arguments(self, parser):
        parser.add_argument(
            'stream',
            help='The Antares stream to listen to'
        )

    def handle(self, *args, **options):
        stream = options['stream']
        broker_class = get_service_class('Antares')
        broker = broker_class()
        broker.run_stream({'stream': stream})
