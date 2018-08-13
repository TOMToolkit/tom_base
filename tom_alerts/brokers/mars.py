import requests
from urllib.parse import urlencode
from tom_alerts.alerts import GenericAlert
from dateutil.parser import parse
from django import forms

from tom_alerts.alerts import GenericQueryForm

MARS_URL = 'https://mars.lco.global'


class MARSQueryForm(GenericQueryForm):
    time_lower = forms.DateField(required=False)
    time_upper = forms.DateField(required=False)
    jd_lower = forms.FloatField(required=False)
    jd_upper = forms.FloatField(required=False)
    filter = forms.CharField(required=False)
    cone_search = forms.CharField(required=False)
    cone_search_object = forms.CharField(required=False)
    nearby_objects = forms.CharField(required=False)
    ra_lower = forms.FloatField(required=False)
    ra_upper = forms.FloatField(required=False)
    dec_lower = forms.FloatField(required=False)
    dec_upper = forms.FloatField(required=False)
    l_lower = forms.FloatField(required=False)
    l_upper = forms.FloatField(required=False)
    b_lower = forms.FloatField(required=False)
    b_upper = forms.FloatField(required=False)
    magpsf_lower = forms.FloatField(required=False)
    magpsf_upper = forms.FloatField(required=False)
    sigmapsf_less_than = forms.FloatField(required=False)
    magap_lower = forms.FloatField(required=False)
    magap_upper = forms.FloatField(required=False)
    distnr_lower = forms.FloatField(required=False)
    distnr_upper = forms.FloatField(required=False)
    delta_mag_lower = forms.FloatField(required=False)
    delta_mag_upper = forms.FloatField(required=False)
    delta_mag_ref_lower = forms.FloatField(required=False)
    delta_mag_ref_upper = forms.FloatField(required=False)
    rb_greater_than = forms.FloatField(required=False)
    classtar_lower = forms.FloatField(required=False)
    classtar_upper = forms.FloatField(required=False)
    fwhm_greater_than = forms.FloatField(required=False)


class MARSBroker(object):
    name = 'MARS'
    form = MARSQueryForm

    @classmethod
    def fetch_alerts(clazz, page, **kwargs):
        args = urlencode(kwargs)
        url = f'{MARS_URL}/?page={page}&format=json&{args}'
        alerts = []
        response = requests.get(url)
        response.raise_for_status()
        parsed = response.json()
        alerts = parsed['results']
        if parsed['has_next']:
            page += 1
            alerts += clazz.fetch_alerts(page, kwargs)
        return [clazz.to_generic_alert(alert) for alert in alerts]

    @classmethod
    def fetch_alert(clazz, id):
        url = f'{MARS_URL}/{id}/'
        response = requests.get(url)
        response.raise_for_status()
        parsed = response.json()
        return clazz.to_generic_alert(parsed)

    @classmethod
    def to_generic_alert(clazz, mars_alert):
        timestamp = parse(mars_alert['wall_time'])

        return GenericAlert(
                timetamp=timestamp,
                source=clazz.name,
                ra=mars_alert['ra'],
                dec=mars_alert['dec'],
                mag=mars_alert['magpsf'],
                score=mars_alert['rb']
        )


