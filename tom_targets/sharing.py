import requests

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
