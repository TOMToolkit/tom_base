import requests
from urllib.parse import urlencode
from dateutil.parser import parse
from astropy import units as u
from astropy.coordinates import Angle


from tom_alerts.alerts import GenericAlert
from tom_alerts.alerts import GenericQueryForm
from tom_targets.models import Target, TargetExtra

SCOUT_URL = 'https://ssd-api.jpl.nasa.gov/scout.api'


class ScoutQueryForm(GenericQueryForm):
    pass


def hours_min_to_decimal(val):
    hours, minutes = val.split(':')
    angle = Angle('{0}h{1}m'.format(hours, minutes))
    return angle.to(u.degree).value


class ScoutBroker:
    name = 'Scout'
    form = ScoutQueryForm

    @classmethod
    def clean_parameters(clazz, parameters):
        parameters.pop('query_name')
        parameters.pop('broker')
        return {k.replace('_', '-'): v for k, v in parameters.items() if v}

    @classmethod
    def fetch_alerts(clazz, parameters):
        args = urlencode(clazz.clean_parameters(parameters))
        url = '{0}?{1}'.format(SCOUT_URL, args)
        response = requests.get(url)
        response.raise_for_status()
        parsed = response.json()['data']
        parsed.sort(key=lambda x: parse(x['lastRun']), reverse=True)
        return parsed

    @classmethod
    def fetch_alert(clazz, id):
        url = f'{SCOUT_URL}/{id}/?format=json'
        url = '{0}?tdes={1}'.format(SCOUT_URL, id)
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    @classmethod
    def process_reduced_data(clazz, target, alert=None):
        pass

    @classmethod
    def to_target(clazz, alert):
        target = Target.objects.create(
            identifier=alert['objectName'],
            name=alert['objectName'],
            type='NON_SIDEREAL',
            ra=hours_min_to_decimal(alert['ra']),
            dec=alert['dec'],
            eccentricity=alert['elong']
        )
        for k, v in alert.items():
            if k not in ['objectName', 'ra', 'dec'] and v:
                TargetExtra.objects.create(target=target, key=k, value=v)

        return target

    @classmethod
    def to_generic_alert(clazz, alert):
        timestamp = parse(alert['lastRun'])
        url = 'https://cneos.jpl.nasa.gov/scout/#/object/' + alert['objectName']

        return GenericAlert(
            timestamp=timestamp,
            url=url,
            id=alert['objectName'],
            name=alert['objectName'],
            ra=hours_min_to_decimal(alert['ra']),
            dec=alert['dec'],
            mag=alert['H'],
            score=alert['neoScore']
        )
