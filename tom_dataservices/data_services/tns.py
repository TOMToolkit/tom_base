import requests
import json

from django import forms
from crispy_forms.layout import Div, Fieldset, HTML, Layout

from tom_dataservices.dataservices import BaseDataService
from tom_dataservices.forms import BaseQueryForm
from tom_targets.models import Target


class TNSForm(BaseQueryForm):
    target_name = forms.CharField(required=False,
                                  label='Target (IAU) Name',
                                  help_text='Omit the AT or SN prefix')
    internal_name = forms.CharField(required=False,
                                    label='Internal (Survey) Name')
    ra = forms.FloatField(required=False, min_value=0., max_value=360.,
                          label='R.A.',
                          help_text='Right ascension in degrees')
    dec = forms.FloatField(required=False, min_value=-90., max_value=90.,
                           label='Dec.',
                           help_text='Declination in degrees')
    radius = forms.FloatField(required=False, min_value=0.,
                              label='Cone Radius')
    units = forms.ChoiceField(required=False,
                              label='Radius Units',
                              choices=[('', ''), ('arcsec', 'arcsec'), ('arcmin', 'arcmin'), ('deg', 'deg')])
    days_ago = forms.FloatField(required=False, min_value=0.,
                                label='Discovered in the Last __ Days',
                                help_text='Leave blank to use the "Discovered After" field')
    min_date = forms.CharField(required=False,
                               label='Discovered After',
                               help_text='Most valid date formats are recognized')
    days_from_nondet = forms.FloatField(required=False, min_value=0.,
                                        label='Days From Nondetection',
                                        help_text='Maximum time between last nondetection and first detection')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            HTML('''
                <p>
                Please see <a href="https://wis-tns.weizmann.ac.il/sites/default/files/api/TNS_APIs_manual.pdf"
                target="_blank">the TNS API Manual</a> for a detailed description of available filters.
                </p>
            '''),
            'internal_name',
            Fieldset(
                'Cone Search',
                Div(
                    Div(
                        'ra',
                        'radius',
                        css_class='col',
                    ),
                    Div(
                        'dec',
                        'units',
                        css_class='col',
                    ),
                    css_class="form-row",
                )
            ),
            Fieldset(
                'Discovery Date',
                Div(
                    Div('days_ago', css_class='col'),
                    Div('min_date', css_class='col'),
                    css_class='form-row'
                ),
                'days_from_nondet'
            ),
        )


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
    query_results_table = 'tom_dataservices/tns/partials/tns_query_results_table.html'

    def get_simple_form_partial(self):
        """Returns a path to a simplified bare-minimum partial form that can be used to access the DataService."""
        return 'tom_dataservices/tns/partials/tns_simple_form.html'

    # def get_advanced_form_partial(self):
    #     """Returns a path to a full or advanced partial form that can be used to access the DataService."""
    #     return 'tom_dataservices/tns/partials/tns_advanced_form.html'

    @classmethod
    def urls(cls, **kwargs) -> dict:
        """Dictionary of URLS for the TNS API."""
        urls = super().urls()
        urls['base_url'] = cls.get_configuration('base_url', 'https://sandbox.wis-tns.org')
        urls['object_url'] = f'{urls["base_url"]}/api/get/object'
        urls['search_url'] = f'{urls["base_url"]}/api/get/search'
        return urls

    def build_headers(self, *args, **kwargs):
        # More info about this user agent header can be found here.
        # https://www.wis-tns.org/content/tns-newsfeed#comment-wrapper-23710
        return {
            'User-Agent': f'tns_marker{{"tns_id": "{self.get_configuration("bot_id")}", '
                          f'"type": "bot", "name": "{self.get_configuration("bot_name")}"}}'
            }

    def build_query_parameters(self, parameters, **kwargs):
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
                'objname': parameters.get('objname', ''),
                'photometry': 0,
                'spectroscopy': 0,
            }
            )
        }
        self.query_parameters = data
        return data

    def query_service(self, data, **kwargs):
        response = requests.post(kwargs['url'], data, headers=self.build_headers())
        response.raise_for_status()
        json_response = response.json()
        self.query_results = json_response['data']
        return self.query_results

    def query_targets(self, query_parameters):
        """Set up and run a specialized query for retrieving targets from a DataService."""
        targets = []
        results = self.query_service(query_parameters, url=self.get_urls('search_url'))
        for result in results:
            target_parameters = self.build_query_parameters(result)
            target_data = self.query_service(target_parameters, url=self.get_urls('object_url'))
            targets.append(target_data)
        return targets

    def get_form_class(self):
        return TNSForm

    def create_target_from_query(self, query_results, **kwargs):
        """
            Returns a Target instance for an object defined by an alert, as well as
            any TargetExtra or additional TargetNames.

            :returns: representation of object for an alert
            :rtype: `Target`

            :returns: dict of extras to be added to the new Target
            :rtype: `dict`

            :returns: list of aliases to be added to the new Target
            :rtype: `list`
        """

        target = Target(
            name=query_results['name_prefix'] + query_results['objname'],
            type='SIDEREAL',
            ra=query_results['radeg'],
            dec=query_results['decdeg']
        )
        return target, {}, []
