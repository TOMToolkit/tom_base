import requests
import os

from django.conf import settings

from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, DataProductGroup, ReducedDatum
from tom_dataproducts.alertstreams.hermes import publish_photometry_to_hermes, BuildHermesMessage
from tom_dataproducts.serializers import DataProductSerializer


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
    headers = {'Media-Type': 'application/json'}

    dataproducts_url = destination_tom_base_url + 'api/dataproducts/'
    targets_url = destination_tom_base_url + 'api/targets/'
    reduced_datums = ReducedDatum.objects.none()
    if product_id:
        product = DataProduct.objects.get(pk=product_id)
        target = product.target
        serialized_data = DataProductSerializer(product).data
    # elif selected_data:
    #     reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
    # elif target_id:
    #     target = Target.objects.get(pk=target_id)
    #     data_type = form_data['data_type']
    #     reduced_datums = ReducedDatum.objects.filter(target=target, data_type=data_type)
    else:
        return {'message': f'ERROR: No valid data to share.'}

    # get destination Target
    target_response = requests.get(f'{targets_url}?name={target.name}', headers=headers, auth=auth)
    target_response_json = target_response.json()
    if target_response_json['results']:
        destination_target_id = target_response_json['results'][0]['id']
    else:
        return target_response

    serialized_data['target'] = destination_target_id

    # TODO: this should be updated when tom_dataproducts is updated to use django.core.storage
    dataproduct_filename = os.path.join(settings.MEDIA_ROOT, product.data.name)
    # Save DataProduct in Destination TOM
    with open(dataproduct_filename, 'rb') as dataproduct_filep:
        files = {'file': (product.data.name, dataproduct_filep, 'text/csv')}
        headers = {'Media-Type': 'multipart/form-data'}
        response = requests.post(dataproducts_url, data=serialized_data, files=files,
                                 headers=headers, auth=auth)
    return response
    # serialized_target_data = TargetSerializer(target).data
    # TODO: Make sure aliases are checked before creating new target
    # Attempt to create Target in Destination TOM
    # response = requests.post(targets_url, headers=headers, auth=auth, data=serialized_target_data)
    # try:
    #     target_response = response.json()
    #     destination_target_id = target_response['id']
    # except KeyError:
    #     # If Target already exists at destination, find ID
    #     response = requests.get(targets_url, headers=headers, auth=auth, data=serialized_target_data)
    #     target_response = response.json()
    #     destination_target_id = target_response['results'][0]['id']


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
