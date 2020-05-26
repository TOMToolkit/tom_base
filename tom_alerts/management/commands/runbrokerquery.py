from django.core.management.base import BaseCommand

from tom_alerts.models import BrokerQuery
from tom_alerts.alerts import get_service_class
from time import sleep


class Command(BaseCommand):
    help = 'Runs saved alert queries and saves the results as Targets'

    def add_arguments(self, parser):
        parser.add_argument(
            'query_name',
            help='One or more saved queries to run'
        )

    def handle(self, *args, **options):
        try:
            query = BrokerQuery.objects.get(name=options['query_name'])
            broker_class = get_service_class(query.broker)
            broker = broker_class()
            alerts = broker.fetch_alerts(query.parameters_as_dict)
            while True:
                try:
                    generic_alert = broker.to_generic_alert(next(alerts))
                    target = generic_alert.to_target()
                    target.save()
                    self.stdout.write('Created target: {}'.format(target))
                except StopIteration:
                    self.stdout.write('Finished creating targets')
                sleep(1)
        except KeyboardInterrupt:
            self.stdout.write('Exiting...')
