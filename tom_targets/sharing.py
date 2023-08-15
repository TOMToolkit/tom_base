import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tom_targets.serializers import TargetSerializer
from tom_dataproducts.sharing import get_destination_target


def share_target_with_tom(share_destination, form_data, group_list=()):
    """

    :param share_destination:
    :param form_data:
    :param group_list:
    :return:
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
    target_create_response = []
    if target_search_response.status_code != 200:
        return target_search_response
    if destination_target_id is None:
        # If target is not in Destination, serialize and create new target.
        serialized_target = TargetSerializer(form_data['target']).data
        # Overwrite local Groups
        serialized_target['groups'] = [{'name': f'Imported From {settings.TOM_NAME}'}]
        for group in group_list:
            serialized_target['groups'].append({'name': group.name})
        target_create_response = requests.post(targets_url, json=serialized_target, headers=headers, auth=auth)

    return target_create_response
