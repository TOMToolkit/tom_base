from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError

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
            alerts = broker.fetch_alerts(query.parameters)
            for alert in alerts:
                try:
                    generic_alert = broker.to_generic_alert(alert)
                    target, extras, aliases = generic_alert.to_target()
                    target.full_clean()  # Top Priority is checking that target is unique.
                    target.save(extras=extras, names=aliases)
                    self.stdout.write('Created target: {}'.format(target))
                except ValidationError as e:
                    self.stdout.write(f'WARNING for {target.name}: {e}')
            self.stdout.write('Finished creating targets')
        except KeyboardInterrupt:
            self.stdout.write('Exiting...')
