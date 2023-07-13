import requests
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.alertstreams.hermes import publish_photometry_to_hermes, BuildHermesMessage, get_hermes_topics
from tom_dataproducts.serializers import DataProductSerializer, ReducedDatumSerializer


def share_data_with_hermes(share_destination, form_data, product_id=None, target_id=None, selected_data=None):
    """

    :param share_destination:
    :param form_data:
    :param product_id:
    :param target_id:
    :param selected_data:
    :return:
    """
    # Query relevant Reduced Datums Queryset
    accepted_data_types = ['photometry']
    if product_id:
        product = DataProduct.objects.get(pk=product_id)
        reduced_datums = ReducedDatum.objects.filter(data_product=product)
    elif selected_data:
        reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
    elif target_id:
        target = Target.objects.get(pk=target_id)
        data_type = form_data['data_type']
        reduced_datums = ReducedDatum.objects.filter(target=target, data_type=data_type)
    else:
        reduced_datums = ReducedDatum.objects.none()

    reduced_datums.filter(data_type__in=accepted_data_types)

    # Build and submit hermes table from Reduced Datums
    hermes_topic = share_destination.split(':')[1]
    destination = share_destination.split(':')[0]
    message_info = BuildHermesMessage(title=form_data['share_title'],
                                      submitter=form_data['submitter'],
                                      authors=form_data['share_authors'],
                                      message=form_data['share_message'],
                                      topic=hermes_topic
                                      )
    # Run ReducedDatums Queryset through sharing protocols to make sure they are safe to share.
    filtered_reduced_datums = check_for_share_safe_datums(destination, reduced_datums, topic=hermes_topic)
    if filtered_reduced_datums.count() > 0:
        response = publish_photometry_to_hermes(message_info, filtered_reduced_datums)
    else:
        return {'message': f'ERROR: No valid data to share. (Check Sharing Protocol. Note that data types must be in '
                           f'{accepted_data_types})'}
    return response


def share_data_with_tom(share_destination, form_data, product_id=None, target_id=None, selected_data=None):
    """

    :param share_destination:
    :param form_data:
    :param product_id:
    :param target_id:
    :param selected_data:
    :return:
    """
    try:
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']
        username = settings.DATA_SHARING[share_destination]['USERNAME']
        password = settings.DATA_SHARING[share_destination]['PASSWORD']
    except KeyError as err:
        raise ImproperlyConfigured(f'Check DATA_SHARING configuration for {share_destination}: Key {err} not found.')
    auth = (username, password)
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    dataproducts_url = destination_tom_base_url + 'api/dataproducts/'
    targets_url = destination_tom_base_url + 'api/targets/'
    reduced_datums_url = destination_tom_base_url + 'api/reduceddatums/'
    reduced_datums = ReducedDatum.objects.none()

    if product_id:
        product = DataProduct.objects.get(pk=product_id)
        target = product.target
        serialized_data = DataProductSerializer(product).data
        destination_target_id = get_destination_target(target, targets_url, headers, auth)
        if destination_target_id is None:
            return {'message': 'ERROR: No matching target found.'}
        serialized_data['target'] = destination_target_id
        # TODO: this should be updated when tom_dataproducts is updated to use django.core.storage
        dataproduct_filename = os.path.join(settings.MEDIA_ROOT, product.data.name)
        # Save DataProduct in Destination TOM
        with open(dataproduct_filename, 'rb') as dataproduct_filep:
            files = {'file': (product.data.name, dataproduct_filep, 'text/csv')}
            headers = {'Media-Type': 'multipart/form-data'}
            response = requests.post(dataproducts_url, data=serialized_data, files=files, headers=headers, auth=auth)
    elif selected_data or target_id:
        if selected_data:
            reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
            targets = set(reduced_datum.target for reduced_datum in reduced_datums)
            target_dict = {}
            for target in targets:
                # get destination Target
                destination_target_id = get_destination_target(target, targets_url, headers, auth)
                target_dict[target.name] = destination_target_id
            if all(value is None for value in target_dict.values()):
                return {'message': 'ERROR: No matching targets found.'}
        else:
            target = Target.objects.get(pk=target_id)
            reduced_datums = ReducedDatum.objects.filter(target=target)
            destination_target_id = get_destination_target(target, targets_url, headers, auth)
            if destination_target_id is None:
                return {'message': 'ERROR: No matching target found.'}
            target_dict = {target.name:  destination_target_id}
        response_codes = []
        reduced_datums = check_for_share_safe_datums(share_destination, reduced_datums)
        for datum in reduced_datums:
            if target_dict[datum.target.name]:
                serialized_data = ReducedDatumSerializer(datum).data
                serialized_data['target'] = target_dict[datum.target.name]
                serialized_data['data_product'] = ''
                if not serialized_data['source_name']:
                    serialized_data['source_name'] = settings.TOM_NAME
                    serialized_data['source_location'] = "TOM-TOM Direct Sharing"
                response = requests.post(reduced_datums_url, json=serialized_data, headers=headers, auth=auth)
                response_codes.append(response.status_code)
        failed_data_count = response_codes.count(500)
        if failed_data_count < len(response_codes):
            return {'message': f'{len(response_codes)-failed_data_count} of {len(response_codes)} '
                               'datums successfully saved.'}
        else:
            return {'message': 'ERROR: No valid data shared. These data may already exist in target TOM.'}
    else:
        return {'message': 'ERROR: No valid data to share.'}

    return response


def get_destination_target(target, targets_url, headers, auth):
    target_response = requests.get(f'{targets_url}?name={target.name}', headers=headers, auth=auth)
    target_response_json = target_response.json()
    try:
        if target_response_json['results']:
            destination_target_id = target_response_json['results'][0]['id']
            return destination_target_id
        else:
            return None
    except KeyError:
        return None


def check_for_share_safe_datums(destination, reduced_datums, **kwargs):
    """
    Custom sharing protocols used to determine when data is shared with a destination.
    This example prevents sharing if a datum has already been published to the given Hermes topic.
    :param destination: sharing destination string
    :param reduced_datums: selected input datums
    :return: queryset of reduced datums to be shared
    """
    return reduced_datums
    # if 'hermes' in destination:
    #     message_topic = kwargs.get('topic', None)
    #     # Remove data points previously shared to the given topic
    #     filtered_datums = reduced_datums.exclude(Q(message__exchange_status='published')
    #                                              & Q(message__topic=message_topic))
    # else:
    #     filtered_datums = reduced_datums
    # return filtered_datums


def check_for_save_safe_datums():
    return


def get_sharing_destination_options():
    """
    Build the Display options and headers for the dropdown form for choosing sharing topics.
    Customize for a different selection experience.
    :return: Tuple: Possible Destinations and their Display Names
    """
    choices = []
    try:
        for destination, details in settings.DATA_SHARING.items():
            new_destination = [details.get('DISPLAY_NAME', destination)]
            if details.get('USER_TOPICS', None):
                # If topics exist for a destination (Such as HERMES) give topics as sub-choices
                #   for non-selectable Destination
                if destination == "hermes":
                    destination_topics = get_hermes_topics()
                else:
                    destination_topics = details['USER_TOPICS']
                topic_list = [(f'{destination}:{topic}', topic) for topic in destination_topics]
                new_destination.append(tuple(topic_list))
            else:
                # Otherwise just use destination as option
                new_destination.insert(0, destination)
            choices.append(tuple(new_destination))
    except AttributeError:
        pass
    return tuple(choices)
