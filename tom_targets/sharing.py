import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tom_targets.serializers import TargetSerializer
from tom_targets.models import PersistentShare
from tom_dataproducts.sharing import (check_for_share_safe_datums, share_data_with_tom,
                                      get_destination_target, sharing_feedback_converter)
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.alertstreams.hermes import publish_to_hermes, BuildHermesMessage


def share_target_and_all_data(share_destination, target):
    """
    Given a sharing destination, shares the target and all its current dataproducts
    with that destination. Will raise an Exception is any portion of sharing fails.
    :param share_destination: String sharing destination from the DATA_SHARING setting
    :param target: Target instance that should be shared with all its data
    """
    if 'HERMES' in share_destination.upper():
        hermes_topic = share_destination.split(':')[1]
        destination = share_destination.split(':')[0]
        filtered_reduced_datums = check_for_share_safe_datums(
            destination, ReducedDatum.objects.filter(target=target), topic=hermes_topic)
        sharing = getattr(settings, "DATA_SHARING", {})
        tom_name = f"{getattr(settings, 'TOM_NAME', 'TOM Toolkit')}"
        message = BuildHermesMessage(title=f"Setting up continuous sharing for {target.name} from "
                                     f"{tom_name}.",
                                     authors=sharing.get('hermes', {}).get('DEFAULT_AUTHORS', None),
                                     submitter='',
                                     message='',
                                     topic=hermes_topic
                                     )
        return sharing_feedback_converter(publish_to_hermes(message, filtered_reduced_datums))
    else:
        response = share_target_with_tom(share_destination, {'target': target})
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
        if 'HERMES' in share_destination.upper():
            hermes_topic = share_destination.split(':')[1]
            destination = share_destination.split(':')[0]
            filtered_reduced_datums = check_for_share_safe_datums(
                destination, ReducedDatum.objects.filter(pk__in=reduced_datum_pks), topic=hermes_topic)
            sharing = getattr(settings, "DATA_SHARING", {})
            tom_name = f"{getattr(settings, 'TOM_NAME', 'TOM Toolkit')}"
            message = BuildHermesMessage(title=f"Updated data for {target.name} from "
                                         f"{tom_name}.",
                                         authors=sharing.get('hermes', {}).get('DEFAULT_AUTHORS', None),
                                         submitter=tom_name,
                                         message='',
                                         topic=hermes_topic
                                         )
            publish_to_hermes(message, filtered_reduced_datums)
        else:
            share_data_with_tom(share_destination, None, None, None, selected_data=reduced_datum_pks)


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
