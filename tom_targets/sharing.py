import requests
import base64
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tom_targets.serializers import TargetSerializer
from tom_dataproducts.sharing import get_destination_target


def share_target_with_tom(share_destination, form_data, target_lists=()):
    """
    Share a target with a remote TOM.
    :param share_destination: The name of the destination TOM as defined in settings.DATA_SHARING
    :param form_data: The form data from the target form
    :param target_lists: The target lists to add the target to in the destination TOM
    :return: The response from the destination TOM
    """
    # Try to get destination tom authentication/URL information
    try:
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']
        username = settings.DATA_SHARING[share_destination]['USERNAME']
        password = settings.DATA_SHARING[share_destination]['PASSWORD']
    except KeyError as err:
        raise ImproperlyConfigured(f'Check DATA_SHARING configuration for {share_destination}: Key {err} not found.')
    auth = (username, password)
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    # establish destination TOM URLs
    targets_url = destination_tom_base_url + 'api/targets/'

    # Check if target already exists in destination DB
    destination_target_id, target_search_response = get_destination_target(form_data['target'], targets_url, headers,
                                                                           auth)
    # Handle errors or multiple targets found
    if target_search_response.status_code != 200:
        return target_search_response
    elif isinstance(destination_target_id, list) and len(destination_target_id) > 1:
        return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}

    # Build list of targetlists to add target to in destination TOM
    target_dict_list = [{'name': f'Imported From {settings.TOM_NAME}'}]
    for target_list in target_lists:
        target_dict_list.append({'name': target_list.name})

    # Create or update target in destination TOM
    if destination_target_id is None:
        # If target is not in Destination, serialize and create new target.
        serialized_target = TargetSerializer(form_data['target']).data
        # Remove local User Groups
        serialized_target['groups'] = []
        # Add target lists
        serialized_target['target_lists'] = target_dict_list
        target_create_response = requests.post(targets_url, json=serialized_target, headers=headers, auth=auth)
    else:
        # Add target to target lists if it already exists in destination TOM
        update_target_data = {'target_lists': target_dict_list}
        update_target_url = targets_url + f'{destination_target_id}/'
        target_create_response = requests.patch(update_target_url, json=update_target_data, headers=headers, auth=auth)
    return target_create_response


def urlencode_hermes_format(hermes_json):
    return base64.urlsafe_b64encode(str.encode(json.dumps(hermes_json))).decode()


def targets_to_hermes_format(group_name, targets, include_data=True):
    """ Takes a list of Target model instances and converts them into hermes json format for preloading
    """
    targets_list = []
    photometry_list = []
    for target in targets:
        target_json, photometry_json = _target_to_hermes_format_helper(target, include_data)
        targets_list.append(target_json)
        photometry_list.extend(photometry_json)
    hermes_format = {
        'title': f"Sharing target list '{group_name}' from {getattr(settings, 'TOM_NAME', 'TOM Toolkit')}.",
        'data': {'targets': targets_list, 'photometry': photometry_list}
    }
    sharing = getattr(settings, "DATA_SHARING", None)
    if sharing and 'hermes' in sharing:
        hermes_format['authors'] = sharing['hermes'].get('DEFAULT_AUTHORS', '')

    return hermes_format


def target_to_hermes_format(target, include_data=True):
    """ Takes a Target model instance and converts it into the hermes json format for preloading
    """
    target_json, photometry_json = _target_to_hermes_format_helper(target, include_data)
    hermes_format = {
        'title': f"Updated data for {target.name} from {getattr(settings, 'TOM_NAME', 'TOM Toolkit')}.",
        'data': {'targets': [target_json], 'photometry': photometry_json}
    }
    sharing = getattr(settings, "DATA_SHARING", None)
    if sharing and 'hermes' in sharing:
        hermes_format['authors'] = sharing['hermes'].get('DEFAULT_AUTHORS', '')

    return hermes_format


def _target_to_hermes_format_helper(target, include_data=True):
    """ Takes a Target model instance and converts it into the hermes json format for preloading
    """
    target_json = {
        'name': target.name,
        'aliases': [alias.name for alias in target.aliases.all()],
    }
    if target.type == 'SIDEREAL':
        target_json['ra'] = f"{target.ra}"
        target_json['dec'] = f"{target.dec}"
        if target.epoch:
            target_json['epoch'] = f"{target.epoch}"
        if target.pm_ra:
            target_json['pm_ra'] = f"{target.pm_ra}"
        if target.pm_dec:
            target_json['pm_dec'] = f"{target.pm_dec}"
        if target.distance:
            target_json['distance'] = f"{target.distance}"
            target_json['distance_units'] = 'pc'
        if target.distance_err:
            target_json['distance_error'] = f"{target.distance_err}"
    elif target.type == 'NON_SIDEREAL':
        target_json['orbital_elements'] = {}
        if target.epoch_of_elements:
            target_json['orbital_elements']['epoch_of_elements'] = f"{target.epoch_of_elements}"
        if target.mean_anomaly:
            target_json['orbital_elements']['mean_anomaly'] = f"{target.mean_anomaly}"
        if target.arg_of_perihelion:
            target_json['orbital_elements']['argument_of_the_perihelion'] = f"{target.arg_of_perihelion}"
        if target.eccentricity:
            target_json['orbital_elements']['eccentricity'] = f"{target.eccentricity}"
        if target.lng_asc_node:
            target_json['orbital_elements']['longitude_of_the_ascending_node'] = f"{target.lng_asc_node}"
        if target.inclination:
            target_json['orbital_elements']['orbital_inclination'] = f"{target.inclination}"
        if target.semimajor_axis:
            target_json['orbital_elements']['semimajor_axis'] = f"{target.semimajor_axis}"
        if target.perihdist:
            target_json['orbital_elements']['perihelion_distance'] = f"{target.perihdist}"
        if target.epoch_of_perihelion:
            target_json['orbital_elements']['epoch_of_perihelion'] = f"{target.epoch_of_perihelion}"
    photometry_json = []
    if include_data:
        # Now add the reduced datums to the message
        reduced_datums = target.reduceddatum_set.filter(data_type='photometry')
        for reduced_datum in reduced_datums.iterator():
            photometry = {
                'target_name': reduced_datum.target.name,
                'date_obs': reduced_datum.timestamp.isoformat(),
                'telescope': reduced_datum.value.get('telescope', ''),
                'instrument': reduced_datum.value.get('instrument', ''),
                'bandpass': reduced_datum.value.get('filter', ''),
                'brightness_unit': reduced_datum.value.get('unit', 'AB mag'),
            }
            if reduced_datum.value.get('magnitude', None):
                photometry['brightness'] = f"{reduced_datum.value['magnitude']}"
            else:
                photometry['limiting_brightness'] = f"{reduced_datum.value.get('limit', None)}"
            if reduced_datum.value.get('magnitude_error', None):
                photometry['brightness_error'] = f"{reduced_datum.value['magnitude_error']}"
            photometry_json.append(photometry)
    return target_json, photometry_json
