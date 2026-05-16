import logging

from django.core.management.base import BaseCommand
from astropy.table import Table

from tom_dataservices.models import DataServiceQuery


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Creates a table of save data service queries.'

    def handle(self, *args, **options):
        ids = []
        names = []
        services = []
        last_runs = []
        queries = DataServiceQuery.objects.all()
        for query in queries:
            ids.append(query.pk)
            names.append(query.name)
            services.append(query.data_service)
            last_runs.append(query.last_run)
        t = Table([ids, names, services, last_runs], names=('ID', 'Name', 'Data Service', 'Last Run'))
        print(t)
