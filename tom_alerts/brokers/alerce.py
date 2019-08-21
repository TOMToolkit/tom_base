import requests
import json

from django import forms
from crispy_forms.layout import Layout, Div, Fieldset, HTML
from astropy.time import Time, TimezoneInfo

from tom_alerts.alerts import GenericQueryForm, GenericBroker, GenericAlert
from tom_targets.models import Target

ALERCE_URL = 'http://alerce.online'
ALERCE_SEARCH_URL = 'http://ztf.alerce.online/query'

class ALeRCEQueryForm(GenericQueryForm):
    nobs__gt = forms.IntegerField(
        required=False,
        label='Non-Detections Lower'
    )
    nobs__lt = forms.IntegerField(
        required=False,
        label='Non-Detections Upper'
    )
    classrf = forms.ChoiceField(
        required=False,
        label='Classifier (Random Forest)',
        choices=[("None", "")] + [(k, k) for k in ["CEPH","DSCT","EB","LPV","RRL","SNe","Other"]]
    )
    pclassrf = forms.FloatField(
        required=False,
        label=''
    )
    ra = forms.IntegerField(
        required=False,
        label='RA'
    )
    dec = forms.IntegerField(
        required=False,
        label='DEC'
    )
    sr = forms.IntegerField(
        required=False,
        label='Search Radius'
    )
    mjd__gt = forms.FloatField(
        required=False,
        label='Min date of first detection (MJD)'
    )
    mjd__lt = forms.FloatField(
        required=False,
        label='Max date of first detection (MJD)'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            Fieldset(
                'Non-Detections',
                Div(
                    Div(
                        'nobs__gt',
                        css_class='col',
                    ),
                    Div(
                        'nobs__lt',
                        css_class='col',
                    ),
                    css_class="form-row",
                )
            ),
            Fieldset(
                'Classification Filters',
                Div(
                    Div(
                        'classrf',
                        css_class='col',
                    ),
                    Div(
                        'pclassrf',
                        css_class='col',
                    ),
                    css_class="form-row",
                )
            ),
            Fieldset(
                'Location Filters',
                'ra',
                'dec',
                'sr'
            ),
            Fieldset(
                'Time Filters',
            ),
            Div(
                    Div(
                        'mjd__gt',
                        css_class='col',
                    ),
                    Div(
                        'mjd__lt',
                        css_class='col',
                    ),
                    css_class="form-row",
                )
        )


class ALeRCEBroker(GenericBroker):
    name = 'ALeRCE'
    form = ALeRCEQueryForm

    def fetch_alerts_payload(self, parameters):
        payload = {
            'page': parameters.get('page', 1),
            'query_parameters': {
            }
        }

        if any([parameters['nobs__gt'], parameters['nobs__lt'], parameters['classrf'], parameters['pclassrf']]):
            filters = {}
            if any([parameters['nobs__gt'], parameters['nobs__lt']]):
                filters['nobs'] = {}
                if parameters['nobs__gt']:
                    filters['nobs']['min'] = parameters['nobs__gt']
                if parameters['nobs__lt']:
                    filters['nobs']['max'] = parameters['nobs__lt']
            if parameters['classrf']:
                filters['classrf'] = parameters['classrf']
            if parameters['pclassrf']:
                filters['pclassrf'] = parameters['pclassrf']
            payload['query_parameters']['filters'] = filters

        if any([parameters['ra'], parameters['dec'], parameters['sr']]):
            coordinates = {}
            if parameters['ra']:
                coordinates['ra'] = parameters['ra']
            if parameters['dec']:
                coordinates['dec'] = parameters['dec']
            if parameters['sr']:
                coordinates['sr'] = parameters['sr']
            payload['query_parameters']['coordinates'] = coordinates

        if any([parameters['mjd__gt'], parameters['mjd__lt']]):
            dates = {'firstmjd': {}}
            if parameters['mjd__gt']:
                dates['firstmjd']['min'] = parameters['mjd__gt']
            if parameters['mjd__lt']:
                dates['firstmjd']['max'] = parameters['mjd__lt']
            payload['query_parameters']['dates'] = dates

        return payload


    def fetch_alerts(self, parameters):
        payload = self.fetch_alerts_payload(parameters)
        print(payload)
        response = requests.post(ALERCE_SEARCH_URL, json=payload)
        response.raise_for_status()
        parsed = response.json()
        alerts = [alert_data for alert, alert_data in parsed['result'].items()]
        if parsed['page'] < parsed['num_pages']:
            parameters['page'] = parameters.get('page', 1) + 1
            alerts += self.fetch_alerts(parameters)
        return iter(alerts)

    def fetch_alert(self, id):
        payload = {
            'query_parameters': {
                'filters': {
                    'oid': id
                }
            }
        }
        response = requests.post(ALERCE_SEARCH_URL, json=payload)
        response.raise_for_status()
        return response.json()['result'][0]


    def to_target(self, alert):
        return Target.objects.create(
            identifier=alert['oid'],
            name=alert['oid'],
            type='SIDEREAL',
            ra=alert['meanra'],
            dec=alert['meandec']
        )

    def to_generic_alert(self, alert):
        if alert['lastmjd']:
            timestamp = Time(alert['lastmjd'], format='mjd', scale='utc').to_datetime(timezone=TimezoneInfo())
        else:
            timestamp = ''
        url = '{0}/{1}/{2}'.format(ALERCE_URL, 'vue/object', alert['oid'])

        return GenericAlert(
            timestamp=timestamp,
            url=url,
            id=alert['oid'],
            name=alert['oid'],
            ra=alert['meanra'],
            dec=alert['meandec'],
            mag=alert['mean_magpsf_g'],
            score=None
        )