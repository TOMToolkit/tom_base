from dateutil.parser import parse
import json
import re
import requests
from requests.exceptions import HTTPError

from astropy.coordinates import SkyCoord
from astropy.time import Time, TimezoneInfo
import astropy.units as u
from bs4 import BeautifulSoup
from django import forms

from tom_alerts.alerts import GenericAlert, GenericBroker, GenericQueryForm
from tom_dataproducts.models import ReducedDatum

BASE_BROKER_URL = 'http://gsaweb.ast.cam.ac.uk'


class GaiaQueryForm(GenericQueryForm):
    target_name = forms.CharField(required=False)
    cone = forms.CharField(
        required=False,
        label='Cone Search',
        help_text='RA,Dec,radius in degrees'
    )

    def clean_cone(self):
        cone = self.cleaned_data['cone']
        if cone:
            cone_params = cone.split(',')
            if len(cone_params) != 3:
                raise forms.ValidationError('Cone search parameters must be in the format \'RA,Dec,Radius\'.')
        return cone

    def clean(self):
        super().clean()
        if not (self.cleaned_data.get('target_name') or self.cleaned_data.get('cone')):
            raise forms.ValidationError('Please enter either a target name or cone search parameters.')
        elif self.cleaned_data.get('target_name') and self.cleaned_data.get('cone'):
            raise forms.ValidationError('Please only enter one of target name or cone search parameters.')


class GaiaBroker(GenericBroker):
    name = 'Gaia'
    form = GaiaQueryForm

    def fetch_alerts(self, parameters):
        """Must return an iterator"""
        response = requests.get(f'{BASE_BROKER_URL}/alerts/alertsindex')
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        script_tags = soup.find_all('script')
        alerts = None

        alerts_pattern = re.compile(r'var alerts = \[(.*?)];')
        for script in script_tags:
            m = alerts_pattern.match(str(script.string).strip())
            if m is not None:
                alerts = '['+m.group(1)+']'
                break

        alert_list = json.loads(alerts)

        if parameters['cone'] is not None and len(parameters['cone']) > 0:
            cone_params = parameters['cone'].split(',')
            parameters['cone_ra'] = float(cone_params[0])
            parameters['cone_dec'] = float(cone_params[1])
            parameters['cone_radius'] = float(cone_params[2])*u.deg
            parameters['cone_centre'] = SkyCoord(float(cone_params[0]),
                                                 float(cone_params[1]),
                                                 frame="icrs", unit="deg")

        filtered_alerts = []
        if parameters.get('target_name'):
            for alert in alert_list:
                if parameters['target_name'] in alert['name']:
                    filtered_alerts.append(alert)

        elif 'cone_radius' in parameters.keys():
            for alert in alert_list:
                c = SkyCoord(float(alert['ra']), float(alert['dec']),
                             frame="icrs", unit="deg")
                if parameters['cone_centre'].separation(c) <= parameters['cone_radius']:
                    filtered_alerts.append(alert)

        else:
            filtered_alerts = alert_list

        return iter(filtered_alerts)

    def fetch_alert(self, target_name):

        alert_list = list(self.fetch_alerts({'target_name': target_name, 'cone': None}))

        if len(alert_list) == 1:
            return alert_list[0]
        else:
            return {}

    def to_generic_alert(self, alert):
        timestamp = parse(alert['obstime'])
        alert_link = alert.get('per_alert', {})['link']
        url = f'{BASE_BROKER_URL}/{alert_link}'

        return GenericAlert(
            timestamp=timestamp,
            url=url,
            id=alert['name'],
            name=alert['name'],
            ra=alert['ra'],
            dec=alert['dec'],
            mag=alert['alertMag'],
            score=1.0
        )

    def process_reduced_data(self, target, alert=None):

        if not alert:
            try:
                alert = self.fetch_alert(target.name)

            except HTTPError:
                raise Exception('Unable to retrieve alert information from broker')

        if alert is not None:
            alert_name = alert['name']
            alert_link = alert.get('per_alert', {})['link']
            lc_url = f'{BASE_BROKER_URL}/alerts/alert/{alert_name}/lightcurve.csv'
            alert_url = f'{BASE_BROKER_URL}/{alert_link}'
        elif target:
            lc_url = f'{BASE_BROKER_URL}/{target.name}/lightcurve.csv'
            alert_url = f'{BASE_BROKER_URL}/alerts/alert/{target.name}/'
        else:
            return

        response = requests.get(lc_url)
        response.raise_for_status()
        html_data = response.text.split('\n')

        for entry in html_data[2:]:
            phot_data = entry.split(',')

            if len(phot_data) == 3:
                if 'untrusted' not in phot_data[2] and 'null' not in phot_data[2]:
                    jd = Time(float(phot_data[1]), format='jd', scale='utc')
                    jd.to_datetime(timezone=TimezoneInfo())

                    value = {
                        'magnitude': float(phot_data[2]),
                        'filter': 'G'
                    }

                    rd, _ = ReducedDatum.objects.get_or_create(
                        timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                        value=value,
                        source_name=self.name,
                        source_location=alert_url,
                        data_type='photometry',
                        target=target)
                    rd.save()

        return
