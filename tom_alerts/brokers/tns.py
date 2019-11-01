from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from django import forms
from django.conf import settings
import requests
import json
from datetime import datetime, timedelta
from crispy_forms.layout import Layout, Div, Fieldset


tns_search_url = 'https://wis-tns.weizmann.ac.il/api/get/search'
tns_object_url = 'https://wis-tns.weizmann.ac.il/api/get/object'


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
    min_date = forms.DateTimeField(required=False,
                                   label='Discovered After',
                                   help_text='Most valid date formats are recognized')
    days_from_nondet = forms.FloatField(required=False, min_value=0.,
                                        label='Days From Nondetection',
                                        help_text='Maximum time between last nondetection and first detection')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
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
    https://wis-tns.weizmann.ac.il/
    """

    name = 'TNS'
    form = TNSForm

    @classmethod
    def fetch_alerts(cls, parameters):
        if parameters['days_ago'] is not None:
            public_timestamp = (datetime.utcnow() - timedelta(days=parameters['days_ago']))\
                .strftime('%Y-%m-%d %H:%M:%S')
        elif parameters['min_date'] is not None:
            public_timestamp = parameters['min_date'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            public_timestamp = ''
        data = {
            'api_key': settings.BROKER_CREDENTIALS['TNS_APIKEY'],
            'data': json.dumps({
                'name': parameters['target_name'],
                'internal_name': parameters['internal_name'],
                'ra': parameters['ra'],
                'dec': parameters['dec'],
                'radius': parameters['radius'],
                'units': parameters['units'],
                'public_timestamp': public_timestamp,
            })
         }
        response = requests.post(tns_search_url, data)
        response.raise_for_status()
        transients = response.json()
        alerts = []
        for transient in transients['data']['reply']:
            data = {
                'api_key': settings.BROKER_CREDENTIALS['TNS_APIKEY'],
                'data': json.dumps({
                    'objname': transient['objname'],
                    'photometry': 1,
                    'spectroscopy': 0,
                })
            }
            response = requests.post(tns_object_url, data)
            response.raise_for_status()
            alert = response.json()['data']['reply']

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
        return iter(alerts)

    @classmethod
    def to_generic_alert(cls, alert):
        return GenericAlert(
            timestamp=alert['discoverydate'],
            url='https://wis-tns.weizmann.ac.il/object/' + alert['name'],
            id=alert['name'],
            name=alert['name_prefix'] + alert['name'],
            ra=alert['radeg'],
            dec=alert['decdeg'],
            mag=alert['discoverymag'],
            score=alert['name_prefix'] == 'SN'
        )
