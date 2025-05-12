from datetime import datetime, timedelta
import requests
import json

from tom_dataservices.dataservices import BaseDataService, MissingDataException
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target


class TNSDataService(BaseDataService):
    """
        The ``TNSDataService`` is the interface to the Transient Name Server. For information regarding the TNS,
        please see https://www.wis-tns.org/

        To include the ``TNSBroker`` in your TOM, add the broker module location to your `TOM_ALERT_CLASSES` list in
        your ``settings.py``:

        .. code-block:: python

            TOM_ALERT_CLASSES = [
                'tom_alerts.brokers.tns.TNSBroker',
                ...
            ]

        Requires the following configuration in settings.py:

        .. code-block:: python

            DATA_Services = {
                'TNS': {
                    'api_key': os.getenv('TNS_API_KEY', 'DO NOT COMMIT API TOKENS TO GIT!'),
                    'bot_id': os.getenv('TNS_BOT_ID ', 'My TNS Bot ID'),
                    'bot_name': os.getenv('TNS_BOT_NAME', 'BestTOMBot'),
                    'base_url': 'https://sandbox.wis-tns.org/',  # Note this is the Sandbox URL
                    'group_name': os.getenv('TNS_GROUP_NAME', 'BestTOMGroup'),
                },
            }

        """
    name = 'TNS'
    info_url = 'https://tom-toolkit.readthedocs.io/en/latest/api/tom_alerts/brokers.html#module-tom_alerts.brokers.tns'

    def urls(self) -> dict:
        """Dictionary of URLS for the TNS API."""
        urls = super().urls()
        urls['base_url'] = self.get_configuration('base_url', 'https://sandbox.wis-tns.org/')
        urls['object_url'] = f'{urls["base_url"]}/api/get/object'
        urls['search_url'] = f'{urls["base_url"]}/api/get/search'
        return urls

    def build_headers(self):
        # More info about this user agent header can be found here.
        # https://www.wis-tns.org/content/tns-newsfeed#comment-wrapper-23710
        return {
            'User-Agent': f'tns_marker{{"tns_id": "{self.get_configuration("bot_id")}", '
                        f'"type": "bot", "name": "{self.get_configuration("bot_name")}"}}'
            }

    def build_query_parameters(self, parameters):
        """
        Args:
            parameters: dictionary containing days_ago (str), min_date (str)
            and either:

            - Right Ascension, declination (can be deg, deg or h:m:s, d:m:s) of the target,
                and search radius and search radius unit ("arcmin", "arcsec", or "deg"), or

            - TNS name without the prefix (eg. 2024aa instead of AT2024aa)

        Returns:
            json containing response from TNS including TNS name and prefix.
        """
        try:
            if parameters['days_ago'] is not None:
                public_timestamp = (datetime.utcnow() - timedelta(days=parameters['days_ago'])) \
                    .strftime('%Y-%m-%d %H:%M:%S')
            elif parameters['min_date'] is not None:
                public_timestamp = parameters['min_date']
            else:
                public_timestamp = ''
        except KeyError:
            raise Exception('Missing fields (days_ago, min_date) from the parameters dictionary.')

        # TNS expects either (ra, dec, radius, unit) or just target_name.
        # target_name has to be a TNS name of the target without a prefix.
        # Unused fields can be empty strings
        data = {
            'api_key': self.get_credentials(),
            'data': json.dumps({
                'name': parameters.get('target_name', ''),
                'internal_name': parameters.get('internal_name', ''),
                'ra': parameters.get('ra', ''),
                'dec': parameters.get('dec', ''),
                'radius': parameters.get('radius', ''),
                'units': parameters.get('units', ''),
                'public_timestamp': public_timestamp,
            }
            )
        }
        self.query_parameters = data
        return data

    def query_service(self, data, **kwargs):
        response = requests.post(self.get_urls('search_url'), data, headers=self.build_headers())
        response.raise_for_status()
        transients = response.json()
        self.query_results = transients
        return transients

    def query_targets(self, query_parameters):
        """Set up and run a specialized query for retrieving targets from a DataService."""
        return self.query_service(query_parameters)

    def get_form_class(self):
        return TestDataServiceForm

    def create_target_from_query(self, query_results, **kwargs):
        return Target(**query_results)
