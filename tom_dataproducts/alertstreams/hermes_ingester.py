import os
import tempfile
import uuid
import json
from urllib.parse import urlparse, urljoin
from dateutil.parser import parse
import logging
import requests

from django.core.files import File
from django.conf import settings

from tom_alerts.models import AlertStreamMessage
from tom_targets.models import Target, TargetList
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.models import DataProduct, ReducedDatum

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_or_create_uuid_from_metadata(metadata) -> uuid.UUID:
    """
    Extract the UUID from the message metadata, or generate a UUID if none present in metadata.

    The headers property of the metadata is a list of tuples of the form [('key', value), ...].
    """
    # get the tuple with the uuid: key is '_id'
    message_uuid_tuple = None
    if metadata.headers:
        message_uuid_tuple = next((item for item in metadata.headers if item[0] == '_id'), None)
    if message_uuid_tuple:
        message_uuid = uuid.UUID(bytes=message_uuid_tuple[1])
    else:
        # this message header metadata didn't have UUID, so make one
        message_uuid = uuid.uuid4()
    return message_uuid


HERMES_SPECTROSCOPY_FILE_EXTENSIONS = ('.fits.fz', '.fits', '.csv', '.txt', '.ascii')


def hermes_alert_handler(alert, metadata):
    """
    Example Alert Handler to record data streamed through Hermes as a new ReducedDatum.

    -- Reads Photometry and Spectroscopy Data (both inline and file-based)
    -- Creates a new Target if no match is found for Target Name or aliases
    -- Does not Ingest Data if exact match already exists
    -- Requires 'tom_alertstreams' in settings.INSTALLED_APPS
    -- Requires ALERT_STREAMS['topic_handlers'] in settings
    """
    alert_as_dict = alert.content
    alert_id = get_or_create_uuid_from_metadata(metadata)
    photometry_table = alert_as_dict['data'].get('photometry') or []
    spectroscopy_table = alert_as_dict['data'].get('spectroscopy') or []
    target_table = alert_as_dict['data'].get('targets', [])
    # Set a hermes_base_url to link ingested messages to
    if hasattr(settings, 'DATA_SHARING'):
        hermes_base_url = settings.DATA_SHARING.get('hermes', {}).get('BASE_URL', 'https://hermes.lco.global')
    else:
        hermes_base_url = 'https://hermes.lco.global'
    hermes_message_url = urljoin(hermes_base_url, f'/message/{alert_id}')

    if not photometry_table and not spectroscopy_table:
        return

    hermes_alert, created = AlertStreamMessage.objects.get_or_create(
        topic=metadata.topic, exchange_status='ingested', message_id=alert_id)

    if not created:
        # Only try to read and ingest the hermes message if we haven't already done so!
        return

    # Cache of target names in alert message -> Target model instance in TOM
    target_cache = {}

    def resolve_target(target_name):
        if target_name not in target_cache:
            # We first attempt to match to an existing target in the TOM by target_name or any specified aliases
            target_entry = next((t for t in target_table if t.get('name', '') == target_name), {}) if target_table else {}
            aliases = target_entry.get('aliases', [])
            query = Target.matches.match_name(target_name)
            if not query:
                for alias in aliases:
                    query = Target.matches.match_name(alias)
                    if query:
                        break
            if query:
                target_cache[target_name] = query[0]
            # If we fail to find a local Target, we will create a target from what's in the alert message
            elif target_table:
                new_target = create_new_hermes_target(target_table, target_name)
                if new_target is not None:
                    target_cache[target_name] = new_target
        return target_cache.get(target_name)

    # Now we ingest all the photometry rows in the alert message
    for row in photometry_table:
        target = resolve_target(row['target_name'])
        if target is None:
            continue

        try:
            obs_date = parse(row['date_obs'])
        except ValueError:
            continue

        datum = {
            'target': target,
            'data_type': 'photometry',
            'source_name': metadata.topic,
            'source_location': hermes_message_url,
            'timestamp': obs_date,
            'value': get_hermes_phot_value(row)
        }
        new_rd, created = ReducedDatum.objects.get_or_create(**datum)
        if created:
            new_rd.message.add(hermes_alert)
            new_rd.save()

    # Now ingest all spectroscopy rows, either by downloading referenced files as a DataProduct or ingesting raw data
    for row in spectroscopy_table:
        target = resolve_target(row['target_name'])
        if target is None:
            continue

        try:
            obs_date = parse(row['date_obs'])
        except ValueError:
            continue

        # If file_info exists on the spectroscopy row, attempt to get a data file url from there
        file_url = _get_spectroscopy_file_url(row.get('file_info') or [])
        if file_url:
            _ingest_hermes_spectroscopy_file(file_url, row, target, hermes_alert, hermes_message_url)
        # Otherwise, check if flux and wavelength arrays of data are specified in the row
        elif row.get('flux') and row.get('wavelength'):
            value = {
                'flux': row['flux'],
                'flux_units': row.get('flux_units', ''),
                'wavelength': row['wavelength'],
                'wavelength_units': row.get('wavelength_units', ''),
            }
            for key in ('telescope', 'instrument', 'reducer', 'observer', 'spec_type', 'flux_type', 'classification',
                        'comments', 'exposure_time', 'setup', 'proprietary_period', 'proprietary_period_units'):
                if row.get(key):
                    value[key] = row[key]
            if row.get('flux_error'):
                value['flux_error'] = row['flux_error']

            datum = {
                'target': target,
                'data_type': 'spectroscopy',
                'source_name': metadata.topic,
                'source_location': hermes_message_url,
                'timestamp': obs_date,
                'value': value,
            }
            new_rd, created = ReducedDatum.objects.get_or_create(**datum)
            if created:
                new_rd.message.add(hermes_alert)
                new_rd.save()


def _get_spectroscopy_file_url(file_info_list):
    """
    Return the URL of the first entry in a file_info list whose filename matches a supported
    spectroscopy file extension, or None if no match is found.
    """
    for entry in file_info_list:
        url = entry.get('url', '')
        filename = os.path.basename(urlparse(url).path)
        for ext in HERMES_SPECTROSCOPY_FILE_EXTENSIONS:
            if filename.lower().endswith(ext):
                return url
    return None


def _ingest_hermes_spectroscopy_file(url, spectroscopy_row, target, hermes_alert, alert_url):
    """
    Downloads a spectroscopy file from the given URL, saves it as a DataProduct, and processes
    it into ReducedDatum objects using the configured spectroscopy data processor.
    Skips the download if a DataProduct with this URL as its product_id already exists.
    """
    filename = os.path.basename(urlparse(url).path)

    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as ex:
        logger.error(f'Failed to download spectroscopy file from {url}: {repr(ex)}')
        return

    spectroscopy_keys = ['date_obs', 'flux_units', 'wavelength_units', 'telescope', 'instrument', 'reducer',
                         'observer', 'spec_type', 'flux_type', 'classification', 'comments', 'exposure_time',
                         'setup', 'proprietary_period', 'proprietary_period_units']
    spectroscopy_data = {key: spectroscopy_row[key] for key in spectroscopy_keys if key in spectroscopy_row and spectroscopy_row[key]}
    # Inject these two extra fields since they should be associated with the ReducedDatums somehow
    spectroscopy_data['source_name'] = hermes_alert.topic
    spectroscopy_data['source_location'] = alert_url

    try:
        dp, created = DataProduct.objects.get_or_create(
            product_id=url,
            defaults={'target': target, 'data_product_type': 'spectroscopy', 'extra_data': json.dumps(spectroscopy_data)},
        )
        if created:
            _, ext = os.path.splitext(filename)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmpfile:
                tmpfile.write(response.content)
                tmpfile_path = tmpfile.name
            try:
                with open(tmpfile_path, 'rb') as f:
                    dp.data.save(filename, File(f), save=True)
            finally:
                os.unlink(tmpfile_path)

        reduced_datums = run_data_processor(dp)
        for rd in reduced_datums:
            rd.message.add(hermes_alert)
    except Exception as ex:
        logger.error(f'Failed to ingest spectroscopy file from {url}: {repr(ex)}')


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
        if phot_data.get('limiting_brightness_error'):
            data_dictionary['limit_error'] = phot_data['limiting_brightness_error']
        if phot_data.get('limiting_brightness_unit'):
            data_dictionary['limit_unit'] = phot_data['limiting_brightness_unit']

    for key in ('observer', 'comments', 'exposure_time', 'catalog'):
        if phot_data.get(key):
            data_dictionary[key] = phot_data[key]

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
