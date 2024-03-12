from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from django import forms
from django.conf import settings
import requests
import json
from datetime import datetime, timedelta
from crispy_forms.layout import Div, Fieldset, HTML, Layout


TNS_BASE_URL = 'https://www.wis-tns.org/'
TNS_OBJECT_URL = f'{TNS_BASE_URL}api/get/object'
TNS_SEARCH_URL = f'{TNS_BASE_URL}api/get/search'


class TNSForm(GenericQueryForm):
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
            self.common_layout,
            'target_name',
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
            )
        )


class TNSBroker(GenericBroker):
    """
    The ``TNSBroker`` is the interface to the Transient Name Server. For information regarding the TNS, please see \
    https://www.wis-tns.org/

    To include the ``TNSBroker`` in your TOM, add the broker module location to your `TOM_ALERT_CLASSES` list in
    your ``settings.py``:

    .. code-block:: python

        TOM_ALERT_CLASSES = [
            'tom_alerts.brokers.tns.TNSBroker',
            ...
        ]

    Requires the following configuration in settings.py:

    .. code-block:: python

        BROKERS = {
            'TNS': {
                'api_key': os.getenv('TNS_API_KEY', 'DO NOT COMMIT API TOKENS TO GIT!'),
                'bot_id': os.getenv('TNS_BOT_ID ', 'My TNS Bot ID'),
                'bot_name': os.getenv('TNS_BOT_NAME', 'BestTOMBot'),
                'tns_base_url': 'https://sandbox.wis-tns.org/api',  # Note this is the Sandbox URL
                'group_name': os.getenv('TNS_GROUP_NAME', 'BestTOMGroup'),
            },
        }

    """

    name = 'TNS'
    form = TNSForm
    help_url = 'https://tom-toolkit.readthedocs.io/en/latest/api/tom_alerts/brokers.html#module-tom_alerts.brokers.tns'

    @classmethod
    def tns_headers(cls):
        # More info about this user agent header can be found here.
        # https://www.wis-tns.org/content/tns-newsfeed#comment-wrapper-23710
        return {
            'User-Agent': 'tns_marker{{"tns_id": "{0}", "type": "bot", "name": "{1}"}}'.format(
                  settings.BROKERS['TNS']['bot_id'],
                  settings.BROKERS['TNS']['bot_name']
                )
            }

    @classmethod
    def fetch_alerts(cls, parameters):
        broker_feedback = ''

        transients = cls.fetch_tns_transients(parameters)

        alerts = []
        for transient in transients['data']['reply']:

            alert = cls.get_tns_object_info(transient)

            if parameters['days_from_nondet'] is not None:
                last_nondet = 0.
                first_det = 9999999.
                for phot in alert['photometry']:
                    if '[Last non detection]' in phot['remarks']:
                        last_nondet = max(last_nondet, phot['jd'])
                    else:
                        first_det = min(first_det, phot['jd'])
                if first_det - last_nondet < parameters['days_from_nondet']:
                    alerts.append(alert)
            else:
                alerts.append(alert)

        return iter(alerts), broker_feedback

    @classmethod
    def to_generic_alert(cls, alert):
        return GenericAlert(
            timestamp=alert['discoverydate'],
            url=f'{TNS_BASE_URL}object/' + alert['objname'],
            id=alert['objname'],
            name=alert['name_prefix'] + alert['objname'],
            ra=alert['radeg'],
            dec=alert['decdeg'],
            mag=alert['discoverymag'],
            score=alert['name_prefix'] == 'SN'
        )

    @classmethod
    def fetch_tns_transients(cls, parameters):
        """
        Args:
            parameters: dictionary containing days_ago (str), min_date (str)
            and either:
                - Right Ascention, declination (can be deg, deg or h:m:s, d:m:s) of the target,
                and search radius and search radius unit ("arcmin", "arcsec", or "deg"), or
                - TNS name without the prefix (eg. 2024aa instead of AT2024aa)
        Returns:
            json containing response from TNS including TNS name and prefix.
        """
        try:
            if parameters['days_ago'] is not None:
                public_timestamp = (datetime.utcnow() - timedelta(days=parameters['days_ago']))\
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
            'api_key': settings.BROKERS['TNS']['api_key'],
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
        response = requests.post(TNS_SEARCH_URL, data, headers=cls.tns_headers())
        response.raise_for_status()
        transients = response.json()

        return transients

    @classmethod
    def get_tns_object_info(cls, parameters):
        """
        Args:
            parameters: dictionary containing objname field with TNS name without the prefix.
        Returns:
            json containing response from TNS including classification and classification reports
        """
        try:
            name = parameters['objname']
        except KeyError:
            raise Exception('Missing field (objname) from parameters dictionary.')
        data = {
            'api_key': settings.BROKERS['TNS']['api_key'],
            'data': json.dumps({
                'objname': name,
                'photometry': 1,
                'spectroscopy': 0,
            }
            )
        }
        response = requests.post(TNS_OBJECT_URL, data, headers=cls.tns_headers())
        response.raise_for_status()
        obj_info = response.json()['data']['reply']

        return obj_info
