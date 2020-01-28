from tom_alerts.alerts import GenericQueryForm, GenericAlert, GenericBroker
from tom_alerts.models import BrokerQuery
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum
from dateutil.parser import parse
from django import forms
from astropy.coordinates import SkyCoord
from astropy.time import Time, TimezoneInfo
import astropy.units as u
import requests
from requests.exceptions import HTTPError
import json
from os import path

BROKER_URL = 'http://gsaweb.ast.cam.ac.uk/alerts/alertsindex'


class GaiaQueryForm(GenericQueryForm):
    target_name = forms.CharField(required=False)
    cone = forms.CharField(
        required=False,
        label='Cone Search',
        help_text='RA,Dec,radius in degrees'
    )

    def clean(self):
        if len(self.cleaned_data['target_name']) == 0 and \
                        len(self.cleaned_data['cone']) == 0:
            raise forms.ValidationError(
                "Please enter either a target name or cone search parameters"
                )


class GaiaBroker(GenericBroker):
    name = 'Gaia'
    form = GaiaQueryForm

    def fetch_alerts(self, parameters):
        """Must return an iterator"""
        response = requests.get(BROKER_URL)
        response.raise_for_status()

        html_data = response.text.split('\n')
        for line in html_data:
            if 'var alerts' in line:
                alerts_data = line.replace('var alerts = ', '')
                alerts_data = alerts_data.replace('\n', '').replace(';', '')

        alert_list = json.loads(alerts_data)

        if parameters['cone'] is not None and len(parameters['cone']) > 0:
            cone_params = parameters['cone'].split(',')
            parameters['cone_ra'] = float(cone_params[0])
            parameters['cone_dec'] = float(cone_params[1])
            parameters['cone_radius'] = float(cone_params[2])*u.deg
            parameters['cone_centre'] = SkyCoord(float(cone_params[0]),
                                                 float(cone_params[1]),
                                                 frame="icrs", unit="deg")

        filtered_alerts = []
        if parameters['target_name'] is not None and \
                len(parameters['target_name']) > 0:
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
        url = BROKER_URL.replace('/alerts/alertsindex', alert['per_alert']['link'])

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

        base_url = BROKER_URL.replace('/alertsindex', '/alert')

        if not alert:
            try:
                alert = self.fetch_alert(target.name)

            except HTTPError:
                raise Exception('Unable to retrieve alert information from broker')

        alert_url = BROKER_URL.replace('/alerts/alertsindex',
                                       alert['per_alert']['link'])

        if alert:
            lc_url = path.join(base_url, alert['name'], 'lightcurve.csv')
        elif target:
            lc_url = path.join(base_url, target.name, 'lightcurve.csv')
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

                    rd, created = ReducedDatum.objects.get_or_create(
                        timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                        value=json.dumps(value),
                        source_name=self.name,
                        source_location=alert_url,
                        data_type='photometry',
                        target=target)
                    rd.save()

        return
