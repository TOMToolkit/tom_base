from django.conf import settings

from tom_alerts.models import AlertStreamMessage

import requests


class BuildHermesMessage(object):
    def __init__(self, title='', submitter='', authors='', message='', **kwargs):
        self.title = title
        self.submitter = submitter
        self.authors = authors
        self.message = message
        self.extra_info = kwargs


def publish_photometry_to_hermes(destination, message_info, datums, **kwargs):
    """
    For now this code submits a typical hermes photometry alert using the datums tied to the dataproduct being
     shared. In the future this should instead send the user to a new tab with a populated hermes form.
    :param destination: target stream (topic included?)
    :param message_info: Dictionary of message information
    :param datums: Reduced Datums to be built into table.
    :return:
    """
    stream_base_url = settings.DATA_SHARING[destination]['BASE_URL']
    submit_url = stream_base_url + 'submit/'
    headers = {}
    hermes_photometry_data = []
    hermes_alert = AlertStreamMessage(topic='hermes.test', exchange_status='published')
    hermes_alert.save()
    for tomtoolkit_photometry in datums:
        tomtoolkit_photometry.message.add(hermes_alert)
        hermes_photometry_data.append(create_hermes_phot_table_row(tomtoolkit_photometry, **kwargs))
    alert = {
        'topic': 'hermes.test',
        'title': message_info.title,
        'author': message_info.submitter,
        'data': {
            'authors': message_info.authors,
            'photometry_data': hermes_photometry_data,
        },
        'message_text': message_info.message,
    }
    alert['data'].update(message_info.extra_info)

    response = requests.post(url=submit_url, json=alert, headers=headers)
    return response


def create_hermes_phot_table_row(datum, **kwargs):
    """Build a row for a Hermes Photometry Table using a TOM Photometry datum"""
    table_row = {
        'photometryId': datum.target.name,
        'dateObs': datum.timestamp.strftime('%x %X'),
        'telescope': datum.value.get('telescope', ''),
        'instrument': datum.value.get('instrument', ''),
        'band': datum.value.get('filter', ''),
        'brightness': datum.value.get('magnitude', ''),
        'brightnessError': datum.value.get('error', ''),
        'brightnessUnit': datum.value.get('unit', 'AB mag'),
    }
    return table_row
