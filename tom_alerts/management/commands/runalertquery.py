from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from tom_targets.models import Target
from tom_alerts.models import BrokerQuery
from tom_alerts.alerts import get_service_class
from tom_observations import facility


class Command(BaseCommand):
    help = 'Run saved alert queries and save the results as Targets'

    def add_arguments(self, parser):
        parser.add_argument(
            'query_name',
            nargs='*',
            help='One or more saved queries to run'
        )

    def handle(self, *args, **options):
        queries = []
        if options['query_name']:
            for query_name in options['query_name']:
                try:
                    queries.append(BrokerQuery.objects.get(name=query_name))
                except ObjectDoesNotExist:
                    self.stdout.write('Could not find query with name {}!'.format(query_name))
        else:
            queries = list(BrokerQuery.objects.all())

        created_targets = []
        for query in queries:
            broker_class = get_service_class(query.broker)
            broker = broker_class()
            created_targets.extend(broker.fetch_and_save_all(query.parameters_as_dict))

        self.stdout.write('Created {} targets'.format(len(created_targets)))
