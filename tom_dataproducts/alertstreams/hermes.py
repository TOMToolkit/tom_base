import logging
from dateutil.parser import parse

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

# from hop.io import Metadata

from tom_alerts.models import AlertStreamMessage
from tom_targets.models import Target, TargetList
from tom_dataproducts.models import ReducedDatum

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HermesMessageException(Exception):
    pass


def get_hermes_data_converter_class():
    return import_string(settings.DATA_SHARING['hermes'].get(
        'DATA_CONVERTER_CLASS', 'tom_dataproducts.alertstreams.hermes.HermesDataConverter'))


class HermesDataConverter():
    """ Class is used to encapsulate getting all the hermes values associated with
        a ReducedDatum for either spectroscopy or photometry or a Target. This class
        can be subclassed and reimplemented for TOMs that store the properties of
        their ReducedDatums in a different way, or store Target props in a different way.
    """
    def __init__(self, validate=True):
        self.validate = validate

    def get_hermes_target(self, target):
        """Build a row for a Hermes Target Table from a TOM BaseTarget Model.
        """
        if target.type == "SIDEREAL":
            target_table_row = {
                'name': target.name,
                'ra': target.ra,
                'dec': target.dec,
            }
            if target.epoch:
                target_table_row['epoch'] = target.epoch
            if target.pm_ra:
                target_table_row['pm_ra'] = target.pm_ra
            if target.pm_dec:
                target_table_row['pm_dec'] = target.pm_dec
        else:
            target_table_row = {
                'name': target.name,
                'orbital_elements': {
                    "epoch_of_elements": target.epoch_of_elements,
                    "eccentricity": target.eccentricity,
                    "argument_of_the_perihelion": target.arg_of_perihelion,
                    "mean_anomaly": target.mean_anomaly,
                    "orbital_inclination": target.inclination,
                    "longitude_of_the_ascending_node": target.lng_asc_node,
                    "semimajor_axis": target.semimajor_axis,
                    "epoch_of_perihelion": target.epoch_of_perihelion,
                    "perihelion_distance": target.perihdist,
                }
            }
        target_table_row['aliases'] = [alias.name for alias in target.aliases.all()]
        return target_table_row

    def get_hermes_photometry(self, datum):
        """Build a row for a Hermes Photometry Table using a TOM Photometry datum
        """
        phot_table_row = {
            'target_name': datum.target.name,
            'date_obs': datum.timestamp.isoformat(),
            'telescope': datum.value.get('telescope'),
            'instrument': datum.value.get('instrument'),
            'bandpass': datum.value.get('filter', ''),
        }
        brightness_unit = convert_astropy_brightness_to_hermes(datum.value.get('unit'))
        if brightness_unit:
            phot_table_row['brightness_unit'] = brightness_unit
        if datum.value.get('magnitude', None):
            phot_table_row['brightness'] = datum.value['magnitude']
        else:
            phot_table_row['limiting_brightness'] = datum.value.get('limit', None)
        error_value = datum.value.get('error', datum.value.get('magnitude_error', None))
        if error_value is not None:
            phot_table_row['brightness_error'] = error_value
        return phot_table_row

    def get_hermes_spectroscopy(self, datum):
        """Build a row for a Hermes Spectroscopy Table using a TOM Spectroscopy datum
           The datum is assumed to have is json value be of the form {1: {flux: 1, wavelength:200}, 2: {},...}
           Or the form {'flux': [1,2,3,...], 'wavelength': [1,2,3,...]}
        """
        flux_list = []
        flux_error_list = []
        wavelength_list = []
        if 'flux' in datum.value and 'wavelength' in datum.value:
            flux_list = datum.value['flux']
            wavelength_list = datum.value['wavelength']
            flux_error_list = datum.value.get('flux_error', datum.value.get('error', []))
        else:
            for entry in datum.value.values():
                if 'flux' in entry:
                    flux_list.append(entry['flux'])
                if 'wavelength' in entry:
                    wavelength_list.append(entry['wavelength'])
                if 'error' in entry:
                    flux_error_list.append(entry['error'])
                if 'flux_error' in entry:
                    flux_error_list.append(entry['flux_error'])

        if self.validate:
            if len(flux_list) != len(wavelength_list):
                msg = f"Spectroscopy Datum {datum.id} has mismatched flux and wavelength values"
                logger.error(msg)
                raise HermesMessageException(msg)
            elif len(flux_list) == 0 or len(wavelength_list) == 0:
                msg = f"Spectroscopy Datum {datum.id} has spectrum data in unknown format."
                msg += "Please implement a custom HermesDatumConverter to support your data format."
                logger.error(msg)
                raise HermesMessageException(msg)
            if flux_error_list and len(flux_error_list) != len(flux_list):
                msg = f"Spectroscopy Datum {datum.id} must have the same number of flux and flux error datapoints"
                logger.error(msg)
                raise HermesMessageException(msg)

        spectroscopy_table_row = {
            'target_name': datum.target.name,
            'date_obs': datum.timestamp.isoformat(),
            'telescope': datum.value.get('telescope'),
            'instrument': datum.value.get('instrument'),
            'reducer': datum.value.get('reducer'),
            'observer': datum.value.get('observer'),
            'flux': flux_list,
            'wavelength': wavelength_list,
            'flux_units': datum.value.get('flux_units'),
            'wavelength_units': convert_astropy_wavelength_to_hermes(datum.value.get('wavelength_units')),
        }
        if flux_error_list:
            spectroscopy_table_row['flux_error'] = flux_error_list

        return spectroscopy_table_row


def convert_astropy_brightness_to_hermes(brightness_unit):
    if not brightness_unit:
        return brightness_unit
    elif brightness_unit.upper() == 'AB' or brightness_unit.upper() == 'ABFLUX':
        return 'AB mag'
    else:
        return brightness_unit


def convert_astropy_wavelength_to_hermes(wavelength_unit):
    if not wavelength_unit:
        return wavelength_unit
    elif wavelength_unit.lower() == 'angstrom' or wavelength_unit == 'AA':
        return 'Å'
    elif wavelength_unit.lower() == 'micron':
        return 'µm'
    elif wavelength_unit.lower() == 'hertz':
        return 'Hz'
    else:
        return wavelength_unit


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


def publish_to_hermes(message_info, datums, targets=Target.objects.none(), **kwargs):
    """
    Submits a typical hermes alert using the photometry and targets supplied to build a photometry table.
    -- Stores an AlertStreamMessage connected to each datum to show that the datum has previously been shared.
    :param message_info: HERMES Message Object created with BuildHermesMessage
    :param datums: Queryset of Reduced Datums to be built into table. (Will also pull in targets)
    :param targets: Queryset of Targets to be built into table.
    :return: response
    """
    if 'BASE_URL' not in settings.DATA_SHARING['hermes']:
        return {'message': 'BASE_URL is not set for hermes in the settings.py DATA_SHARING section'}
    if 'HERMES_API_KEY' not in settings.DATA_SHARING['hermes']:
        return {'message': 'HERMES_API_KEY is not set for hermes in the settings.py DATA_SHARING section'}

    stream_base_url = settings.DATA_SHARING['hermes']['BASE_URL']
    submit_url = stream_base_url + 'api/v0/' + 'submit_message/'
    # You will need your Hermes API key. This can be found on your Hermes profile page.
    headers = {'Authorization': f"Token {settings.DATA_SHARING['hermes']['HERMES_API_KEY']}"}
    try:
        alert = create_hermes_alert(message_info, datums, targets, **kwargs)
    except HermesMessageException as e:
        # We have failed in building a valid hermes message, so report that error back
        return {'message': 'ERROR: ' + str(e)}

    try:
        response = requests.post(url=submit_url, json=alert, headers=headers)
        response.raise_for_status()
        # Only mark the datums as shared if the sharing was successful
        hermes_alert = AlertStreamMessage(
            topic=message_info.topic, message_id=response.json().get('uuid'), exchange_status='published')
        hermes_alert.save()
        for tomtoolkit_photometry in datums:
            tomtoolkit_photometry.message.add(hermes_alert)
    except Exception as ex:
        logger.error(repr(ex))
        logger.error(response.content)
        return response

    return response


def preload_to_hermes(message_info, reduced_datums, targets):
    stream_base_url = settings.DATA_SHARING['hermes']['BASE_URL']
    preload_url = stream_base_url + 'api/v0/submit_message/preload/'
    # You will need your Hermes API key. This can be found on your Hermes profile page.
    headers = {'Authorization': f"Token {settings.DATA_SHARING['hermes']['HERMES_API_KEY']}"}

    alert = create_hermes_alert(message_info, reduced_datums, targets)
    try:
        response = requests.post(url=preload_url, json=alert, headers=headers)
        response.raise_for_status()
        return response.json()['key']
    except Exception as ex:
        logger.error(repr(ex))
        logger.error(response.content)

    return ''


def create_hermes_alert(message_info, datums, targets=Target.objects.none(), **kwargs):
    hermes_photometry_data = []
    hermes_spectroscopy_data = []
    hermes_target_dict = {}

    hermes_data_converter = get_hermes_data_converter_class()(validate=True)
    for datum in datums:
        if datum.target.name not in hermes_target_dict:
            hermes_target_dict[datum.target.name] = hermes_data_converter.get_hermes_target(datum.target)
        if datum.data_type == 'photometry':
            hermes_photometry_data.append(hermes_data_converter.get_hermes_photometry(datum))
        elif datum.data_type == 'spectroscopy':
            hermes_spectroscopy_data.append(hermes_data_converter.get_hermes_spectroscopy(datum))

    # Now go through the targets queryset and ensure we have all of them in the table
    # This is needed since some targets may have no corresponding photometry datums but that is still valid to share
    for target in targets:
        if target.name not in hermes_target_dict:
            hermes_target_dict[target.name] = hermes_data_converter.get_hermes_target(target)

    alert = {
        'topic': message_info.topic,
        'title': message_info.title,
        'submitter': message_info.submitter,
        'authors': message_info.authors,
        'data': {
            'targets': list(hermes_target_dict.values()),
            'photometry': hermes_photometry_data,
            'spectroscopy': hermes_spectroscopy_data,
            'extra_data': message_info.extra_info
        },
        'message_text': message_info.message,
    }
    return alert


def get_hermes_topics(**kwargs):
    """
    Method to retrieve a list of available topics from HOP.
    Intended to be called from forms when building topic list.
    Extend this method to restrict topics for individual users.
    :return: List of writable topics available for TOM.
    """
    topics = cache.get('hermes_writable_topics', [])
    if not topics:
        try:
            stream_base_url = settings.DATA_SHARING['hermes']['BASE_URL']
            submit_url = stream_base_url + "api/v0/profile/"
            headers = {'Authorization': f"Token {settings.DATA_SHARING['hermes']['HERMES_API_KEY']}"}
            response = requests.get(url=submit_url, headers=headers)
            topics = response.json()['writable_topics']
            cache.set('hermes_writable_topics', topics, 86400)
        except (KeyError, requests.exceptions.JSONDecodeError):
            pass
    return topics


def hermes_alert_handler(alert, metadata):
    """Example Alert Handler to record data streamed through Hermes as a new ReducedDatum.
    -- Only Reads Photometry Data
    -- Only ingests Data if exact match for Target Name
    -- Does not Ingest Data if exact match already exists
    -- Requires 'tom_alertstreams' in settings.INSTALLED_APPS
    -- Requires ALERT_STREAMS['topic_handlers'] in settings
    """
    alert_as_dict = alert.content
    photometry_table = alert_as_dict['data'].get('photometry', None)
    # target_table = alert_as_dict['data'].get('targets', None)
    if photometry_table:
        hermes_alert = AlertStreamMessage(topic=alert_as_dict['topic'],
                                          exchange_status='ingested',
                                          message_id=alert_as_dict.get("uuid", None))
        target_name = ''
        query = []
        for row in photometry_table:
            if row['target_name'] != target_name:
                target_name = row['target_name']
                query = Target.matches.match_name(target_name)
            if query:
                target = query[0]
            else:
                # add conditional statements for whether to ingest a target here.
                # target = create_new_hermes_target(target_table, target_name, target_list_name="new_hermes_object")
                continue

            try:
                obs_date = parse(row['date_obs'])
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
        'error': phot_data.get('brightness_error', ''),
        'filter': phot_data['bandpass'],
        'telescope': phot_data.get('telescope', ''),
        'instrument': phot_data.get('instrument', ''),
        'unit': phot_data['brightness_unit'],
    }

    if phot_data.get('brightness', None):
        data_dictionary['magnitude'] = phot_data['brightness']
    elif phot_data.get('limiting_brightness', None):
        data_dictionary['limit'] = phot_data['limiting_brightness']

    return data_dictionary


def create_new_hermes_target(target_table, target_name=None, target_list_name=None):
    """
    Ingest a target into your TOM from Hermes.
    Takes a target_table and a target_name. If no target name is given, every target on the target table will be
    ingested.
    :param target_table: Hermes Target table from a Hermes Message
    :param target_name: Name for individual target to ingest from target table.
    :param target_list_name: Name of TargetList within which new target should be placed.
    :return:
    """
    target = None
    for hermes_target in target_table:
        if target_name == hermes_target['name'] or target_name is None:

            new_target = {"name": hermes_target.pop('name')}
            if "ra" in hermes_target and "dec" in hermes_target:
                new_target['type'] = 'SIDEREAL'
                new_target['ra'] = hermes_target.pop('ra')
                new_target['dec'] = hermes_target.pop('dec')
                new_target['pm_ra'] = hermes_target.pop('pm_ra', None)
                new_target['pm_dec'] = hermes_target.pop('pm_dec', None)
                new_target['epoch'] = hermes_target.pop('epoch', None)
            elif "orbital_elements" in hermes_target:
                orbital_elements = hermes_target.pop('orbital_elements')
                new_target['type'] = 'NON_SIDEREAL'
                new_target['epoch_of_elements'] = orbital_elements.pop('epoch_of_elements', None)
                new_target['mean_anomaly'] = orbital_elements.pop('mean_anomaly', None)
                new_target['arg_of_perihelion'] = orbital_elements.pop('argument_of_the_perihelion', None)
                new_target['eccentricity'] = orbital_elements.pop('eccentricity', None)
                new_target['lng_asc_node'] = orbital_elements.pop('longitude_of_the_ascending_node', None)
                new_target['inclination'] = orbital_elements.pop('orbital_inclination', None)
                new_target['semimajor_axis'] = orbital_elements.pop('semimajor_axis', None)
                new_target['epoch_of_perihelion'] = orbital_elements.pop('epoch_of_perihelion', None)
                new_target['perihdist'] = orbital_elements.pop('perihelion_distance', None)
            aliases = hermes_target.pop('aliases', [])
            target = Target(**new_target)
            target.full_clean()
            target.save(names=aliases, extras=hermes_target)
            if target_list_name:
                target_list, created = TargetList.objects.get_or_create(name=target_list_name)
                if created:
                    logger.debug(f'New target_list created: {target_list_name}')
                target_list.targets.add(target)
    return target
