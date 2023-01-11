import logging
from dateutil.parser import parse

from django.conf import settings

# from hop.io import Metadata

from tom_alerts.models import AlertStreamMessage
from tom_targets.models import Target
from tom_dataproducts.models import ReducedDatum

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BuildHermesMessage(object):
    """
    A HERMES Message Object that can be submitted to HOP through HERMES
    """
    def __init__(self, title='', submitter='', authors='', message='', topic='hermes.test', **kwargs):
        self.title = title
        self.submitter = submitter
        self.authors = authors
        self.message = message
        self.topic = topic
        self.extra_info = kwargs


def publish_photometry_to_hermes(message_info, datums, **kwargs):
    """
    Submits a typical hermes photometry alert using the datums supplied to build a photometry table.
    -- Stores an AlertStreamMessage connected to each datum to show that the datum has previously been shared.
    :param message_info: HERMES Message Object created with BuildHermesMessage
    :param datums: Queryset of Reduced Datums to be built into table.
    :return: response
    """
    stream_base_url = settings.DATA_SHARING['hermes']['BASE_URL']
    submit_url = stream_base_url + 'api/v0/' + 'submit_photometry/'
    headers = {'SCIMMA-API-Auth-Username': settings.DATA_SHARING['hermes']['CREDENTIAL_USERNAME'],
               'SCIMMA-API-Auth-Password': settings.DATA_SHARING['hermes']['CREDENTIAL_PASSWORD']}
    hermes_photometry_data = []
    hermes_alert = AlertStreamMessage(topic=message_info.topic, exchange_status='published')
    hermes_alert.save()
    for tomtoolkit_photometry in datums:
        tomtoolkit_photometry.message.add(hermes_alert)
        hermes_photometry_data.append(create_hermes_phot_table_row(tomtoolkit_photometry, **kwargs))
    alert = {
        'topic': message_info.topic,
        'title': message_info.title,
        'submitter': message_info.submitter,
        'authors': message_info.authors,
        'data': {
            'photometry': hermes_photometry_data,
            'extra_info': message_info.extra_info
        },
        'message_text': message_info.message,
    }

    response = requests.post(url=submit_url, json=alert, headers=headers)
    return response


def create_hermes_phot_table_row(datum, **kwargs):
    """Build a row for a Hermes Photometry Table using a TOM Photometry datum
    """
    table_row = {
        'target_name': datum.target.name,
        'ra': datum.target.ra,
        'dec': datum.target.dec,
        'date': datum.timestamp.isoformat(),
        'telescope': datum.value.get('telescope', ''),
        'instrument': datum.value.get('instrument', ''),
        'band': datum.value.get('filter', ''),
        'brightness_unit': datum.value.get('unit', 'AB mag'),
    }
    if datum.value.get('magnitude', None):
        table_row['brightness'] = datum.value['magnitude']
    else:
        table_row['brightness'] = datum.value.get('limit', None)
        table_row['nondetection'] = True
    if datum.value.get('magnitude_error', None):
        table_row['brightness_error'] = datum.value['magnitude_error']
    return table_row


def get_hermes_topics():
    """
    !CURRENTLY UNUSED!
    Method to retrieve a list of available topics from HOP.
    Intended to be called from forms when building topic list.
    TODO: Retrieve list from HOP, currently unavailable due to authentication issues.
    :return: List of topics available for users
    """
    # stream_base_url = settings.DATA_SHARING['hermes']['BASE_URL']
    # submit_url = stream_base_url + "api/v0/profile/"
    # headers = {'SCIMMA-API-Auth-Username': settings.DATA_SHARING['hermes']['CREDENTIAL_USERNAME'],
    #            'SCIMMA-API-Auth-Password': settings.DATA_SHARING['hermes']['CREDENTIAL_PASSWORD']}
    # user = settings.DATA_SHARING['hermes']['SCIMMA_AUTH_USERNAME']
    # headers = {}

    # response = requests.get(url=submit_url, headers=headers)
    topics = settings.DATA_SHARING['hermes']['USER_TOPICS']
    return topics


def hermes_alert_handler(alert, metadata):
    """Alert Handler to record data streamed through Hermes as a new ReducedDatum.
    -- Only Reads Photometry Data
    -- Only ingests Data if exact match for Target Name
    -- Does not Ingest Data if exact match already exists
    -- Requires 'tom_alertstreams' in settings.INSTALLED_APPS
    -- Requires ALERT_STREAMS['topic_handlers'] in settings
    """
    alert_as_dict = alert.content
    photometry_table = alert_as_dict['data'].get('photometry', None)
    if photometry_table:
        hermes_alert = AlertStreamMessage(topic=alert_as_dict['topic'], exchange_status='ingested')
        for row in photometry_table:
            try:
                target = Target.objects.get(name=row['target_name'])
            except Target.DoesNotExist:
                continue

            try:
                obs_date = parse(row['date'])
            except ValueError:
                continue

            datum = {
                'target': target,
                'data_type': 'photometry',
                'source_name': alert_as_dict['topic'],
                'source_location': 'Hermes via HOP',  # TODO Add message URL here once message ID's exist
                'timestamp': obs_date,
                'value': get_hermes_phot_value(row)
            }
            new_rd, created = ReducedDatum.objects.get_or_create(**datum)
            if created:
                hermes_alert.save()
                new_rd.message.add(hermes_alert)
                new_rd.save()


def get_hermes_phot_value(phot_data):
    """
    Convert Hermes Message format for a row of Photometry table into parameters accepted by the Reduced Datum model
    :param phot_data: Dictionary containing Hermes Photometry table.
    :return: Dictionary containing properly formatted parameters for Reduced_Datum
    """
    data_dictionary = {
        'magnitude_error': phot_data.get('brightness_error', ''),
        'filter': phot_data['band'],
        'telescope': phot_data.get('telescope', ''),
        'instrument': phot_data.get('instrument', ''),
        'unit': phot_data['brightness_unit'],
    }

    if not phot_data.get('nondetection', False):
        data_dictionary['magnitude'] = phot_data['brightness']
    else:
        data_dictionary['limit'] = phot_data['brightness']

    return data_dictionary
