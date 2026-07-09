from tom_targets.base_models import get_target_model_app_label, BaseTarget
import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tom_targets.serializers import TargetSerializer
from tom_targets.models import PersistentShare, get_target_model_class
from tom_dataproducts.sharing import (share_data_with_tom,
                                      get_destination_target, sharing_feedback_converter)


def share_target_and_all_data(share_destination, target, user):
    """
    Given a sharing destination, shares the target and all its current dataproducts
    with that destination. Will raise an Exception is any portion of sharing fails.
    :param share_destination: String sharing destination from the DATA_SHARING setting
    :param target: Target instance that should be shared with all its data
    """
    response = share_target_with_tom(share_destination, {'target': target}, user=user)
    response_feedback = sharing_feedback_converter(response)
    if 'ERROR' in response_feedback.upper():
        return response_feedback
    return sharing_feedback_converter(share_data_with_tom(share_destination, None, target_id=target.id))


def continuous_share_data(target, reduced_datums):
    """
    Triggered when new ReducedDatums are created.
    Shares those ReducedDatums to the sharing destination of any PersistentShares on the target.
    :param target: Target instance that these reduced_datums belong to
    :param reduced_datums: list of ReducedDatum instances to share
    """
    persistentshares = PersistentShare.objects.filter(target=target)
    for persistentshare in persistentshares:
        share_destination = persistentshare.destination
        reduced_datum_pks = [rd.pk for rd in reduced_datums]
        share_data_with_tom(share_destination, None, None, None, selected_data=reduced_datum_pks)


def custom_target_to_extras(target_id) -> list[dict]:
    target_app_label = get_target_model_app_label()
    extra_fields = []
    if target_app_label != 'tom_targets':
        target = get_target_model_class().objects.get(pk=target_id)
        for field in target._meta.get_fields():
            if field not in BaseTarget._meta.get_fields() and field.name not in ['id', 'basetarget_ptr']:
                value = getattr(target, field.name, None)
                if value is not None:
                    extra_fields.append({'key': field.name, 'value': str(value)})

    return extra_fields


def share_target_with_tom(share_destination, form_data, target_lists=(), user=None):
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
        # If the shared target is a custom model custom fields should still be shared.
        # Because the destination TOM might not have the same fields, we convert them to
        # target extras.
        extra_extras = custom_target_to_extras(serialized_target['id'])
        serialized_target['targetextra_set'].extend(extra_extras)
        if user is not None:
            serialized_target['targetextra_set'].append({'key': 'shared_by', 'value': user.username})
        serialized_target['targetextra_set'].append({'key': 'shared_from', 'value': settings.TOM_NAME})
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
