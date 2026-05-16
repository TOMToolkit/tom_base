import logging
from requests import HTTPError
from requests.exceptions import ReadTimeout

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.utils import timezone
from astropy.table import Table

from tom_dataservices.models import DataServiceQuery
from tom_dataservices.dataservices import get_data_service_class, NotConfiguredError
from tom_dataservices.dataservices import MissingDataException, QueryServiceError



logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Runs saved dataservice queries and saves the results as Targets'

    def add_arguments(self, parser):
        parser.add_argument(
            'query_id',
            help='ID of saved query to run. (i.e. 1 or 26). Run listqueries management command to see' \
            'IDs for saved queries'
        )

    def handle(self, *args, **options):
        try:
            query = DataServiceQuery.objects.get(id=options['query_id'])
            dataservice_class = get_data_service_class(query.data_service)
            data_service_class = dataservice_class()
            query_parameters = data_service_class.build_query_parameters(query.parameters)
            query.last_run = timezone.now()
            query.save()

            query_results = data_service_class.query_targets(query_parameters)

            for result in query_results:
                try:
                    target = data_service_class.to_target(result)
                    if target:
                        try:
                            data_service_class.to_reduced_datums(target, result.get('reduced_datums'))
                        except MissingDataException:
                            try:
                                data = data_service_class.query_reduced_data(target)
                                data_service_class.to_reduced_datums(target, data)
                            except QueryServiceError as e:
                                logger.error(f'Error retrieving data from Data Service: {e}')
                except ValidationError as e:
                    logger.error(f'Target Creation failed: {e}')
            self.stdout.write('Finished querying targets')
        except DataServiceQuery.DoesNotExist as e:
            logger.error(f"Failure to run query {options['query_id']}: {e}")
        except HTTPError as e:
            logger.error(f"Issue fetching query results, please try again.: {e}")
        except NotConfiguredError as e:
            logger.error(f"Configuration Error. Please contact your TOM Administrator: {e}")
        except QueryServiceError as e:
            logger.error(f"There was an error with the underlying query service: {e}")
        except ReadTimeout as e:
            logger.error(f"The query service connection timed out: {e}")
        except KeyboardInterrupt:
            self.stdout.write('Exiting...')
