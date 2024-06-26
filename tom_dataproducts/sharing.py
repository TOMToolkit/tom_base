import requests
import os
from io import StringIO
from astropy.table import Table
from astropy.io import ascii

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.utils.text import slugify

from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.alertstreams.hermes import publish_to_hermes, BuildHermesMessage, get_hermes_topics
from tom_dataproducts.serializers import DataProductSerializer, ReducedDatumSerializer


def share_target_list_with_hermes(share_destination, form_data, selected_targets=None, include_all_data=False):
    """
    Serialize and share a set of selected targets and their data with Hermes
    :param share_destination: Topic to share data to. (e.g. 'hermes.test')
    :param form_data: Sharing Form data
    :param selected_targets: List of selected target ids to share
    :param include_all_data: Boolean flag to include all dataproducts when sharing or not
    :return: json response for the sharing
    """
    if selected_targets is None:
        selected_targets = []
    target_list = form_data.get('target_list')
    title_name = f"{target_list.name } target list"
    targets = Target.objects.filter(id__in=selected_targets)
    if include_all_data:
        reduced_datums = ReducedDatum.objects.filter(target__id__in=selected_targets, data_type='photometry')
    else:
        reduced_datums = ReducedDatum.objects.none()
    return _share_with_hermes(share_destination, form_data, title_name, reduced_datums, targets)


def share_data_with_hermes(share_destination, form_data, product_id=None, target_id=None, selected_data=None):
    """
    Serialize and share data with Hermes (hermes.lco.global)
    :param share_destination: Topic to share data to. (e.g. 'hermes.test')
    :param form_data: Sharing Form data
    :param product_id: DataProduct ID (if provided)
    :param target_id: Target ID (if provided)
    :param selected_data: List of ReducedDatum IDs (if provided)
    :return: json response for the sharing
    """
    # Query relevant Reduced Datums Queryset
    accepted_data_types = ['photometry']
    if product_id:
        product = DataProduct.objects.get(pk=product_id)
        target = product.target
        reduced_datums = ReducedDatum.objects.filter(data_product=product)
    elif selected_data:
        reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
        target = reduced_datums[0].target
    elif target_id:
        target = Target.objects.get(pk=target_id)
        reduced_datums = ReducedDatum.objects.none()
    else:
        reduced_datums = ReducedDatum.objects.none()
        target = Target.objects.none()
    title_name = target.name if target else ''
    reduced_datums.filter(data_type__in=accepted_data_types)
    return _share_with_hermes(
        share_destination, form_data, title_name, reduced_datums, targets=Target.objects.filter(pk=target.pk)
    )


def _share_with_hermes(share_destination, form_data, title_name,
                       reduced_datums=ReducedDatum.objects.none(),
                       targets=Target.objects.none()):
    """
    Helper method to serialize and share data with hermes
    :param share_destination: Topic to share data to. (e.g. 'hermes.test')
    :param form_data: Sharing Form data
    :param reduced_datums: filtered queryset of reduced datums to submit
    :return: json response for the sharing
    """
    # Build and submit hermes table from Reduced Datums
    hermes_topic = share_destination.split(':')[1]
    destination = share_destination.split(':')[0]
    sharing = getattr(settings, "DATA_SHARING", {})
    authors = form_data.get('share_authors', sharing.get('hermes', {}).get('DEFAULT_AUTHORS', None))
    message_info = BuildHermesMessage(title=form_data.get('share_title',
                                                          f"Updated data for {title_name} from "
                                                          f"{getattr(settings, 'TOM_NAME', 'TOM Toolkit')}."),
                                      submitter=form_data.get('submitter'),
                                      authors=authors,
                                      message=form_data.get('share_message', None),
                                      topic=hermes_topic
                                      )
    # Run ReducedDatums Queryset through sharing protocols to make sure they are safe to share.
    filtered_reduced_datums = check_for_share_safe_datums(destination, reduced_datums, topic=hermes_topic)
    if filtered_reduced_datums.count() > 0 or targets.count() > 0:
        response = publish_to_hermes(message_info, filtered_reduced_datums, targets)
    else:
        return {'message': 'ERROR: No valid data or targets to share. (Check Sharing Protocol. Note that '
                           'only photometry data types are supported for sharing with hermes'}
    return response


def share_data_with_tom(share_destination, form_data, product_id=None, target_id=None, selected_data=None):
    """
    Serialize and share data with another TOM
    :param share_destination: TOM to share data to as described in settings.DATA_SHARING. (e.g. 'mytom')
    :param form_data: Sharing Form data
    :param product_id: DataProduct ID (if provided)
    :param target_id: Target ID (if provided)
    :param selected_data: List of ReducedDatum IDs (if provided)
    :return:
    """
    # Build destination TOM headers and URL information
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

    # If a DataProduct is provided, share that DataProduct
    if product_id:
        product = DataProduct.objects.get(pk=product_id)
        target = product.target
        serialized_data = DataProductSerializer(product).data
        # Find matching target in destination TOM
        destination_target_id, _ = get_destination_target(target, targets_url, headers, auth)
        if destination_target_id is None:
            return {'message': 'ERROR: No matching target found.'}
        elif isinstance(destination_target_id, list) and len(destination_target_id) > 1:
            return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}
        serialized_data['target'] = destination_target_id
        # TODO: this should be updated when tom_dataproducts is updated to use django.core.storage
        dataproduct_filename = os.path.join(settings.MEDIA_ROOT, product.data.name)
        # Save DataProduct in Destination TOM
        with open(dataproduct_filename, 'rb') as dataproduct_filep:
            files = {'file': (product.data.name, dataproduct_filep, 'text/csv')}
            headers = {'Media-Type': 'multipart/form-data'}
            response = requests.post(dataproducts_url, data=serialized_data, files=files, headers=headers, auth=auth)
    elif selected_data or target_id:
        # If ReducedDatums are provided, share those ReducedDatums
        if selected_data:
            reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
            targets = set(reduced_datum.target for reduced_datum in reduced_datums)
            target_dict = {}
            for target in targets:
                # get destination Target
                destination_target_id, _ = get_destination_target(target, targets_url, headers, auth)
                if isinstance(destination_target_id, list) and len(destination_target_id) > 1:
                    return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}
                target_dict[target.name] = destination_target_id
            if all(value is None for value in target_dict.values()):
                return {'message': 'ERROR: No matching targets found.'}
        else:
            # If Target is provided, share all ReducedDatums for that Target
            # (Will not create New Target in Destination TOM)
            target = Target.objects.get(pk=target_id)
            reduced_datums = ReducedDatum.objects.filter(target=target)
            destination_target_id, _ = get_destination_target(target, targets_url, headers, auth)
            if destination_target_id is None:
                return {'message': 'ERROR: No matching target found.'}
            elif isinstance(destination_target_id, list) and len(destination_target_id) > 1:
                return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}
            target_dict = {target.name:  destination_target_id}
        response_codes = []
        reduced_datums = check_for_share_safe_datums(share_destination, reduced_datums)
        if not reduced_datums:
            return {'message': 'ERROR: No valid data to share.'}
        for datum in reduced_datums:
            if target_dict[datum.target.name]:
                serialized_data = ReducedDatumSerializer(datum).data
                serialized_data['target'] = target_dict[datum.target.name]
                serialized_data['data_product'] = ''
                if not serialized_data['source_name']:
                    serialized_data['source_name'] = settings.TOM_NAME
                    serialized_data['source_location'] = f"ReducedDatum shared from " \
                                                         f"<{settings.TOM_NAME}.url>/api/reduceddatums/{datum.id}/"
                response = requests.post(reduced_datums_url, json=serialized_data, headers=headers, auth=auth)
                response_codes.append(response.status_code)
        failed_data_count = len([rc for rc in response_codes if rc >= 300])
        if failed_data_count < len(response_codes):
            return {'message': f'{len(response_codes)-failed_data_count} of {len(response_codes)} '
                               'datums successfully saved.'}
        else:
            return {'message': 'ERROR: No valid data shared. These data may already exist in target TOM.'}
    else:
        return {'message': 'ERROR: No valid data to share.'}

    return response


def get_destination_target(target, targets_url, headers, auth):
    """
    Retrieve the target ID from a destination TOM that is a fuzzy match the given target name and aliases
    :param target: Target Model
    :param targets_url: Destination API URL for TOM Target List
    :param headers: TOM API headers
    :param auth: TOM API authorization
    :return:
    """
    # Create coma separated list of target names plus aliases that can be recognized and parsed by the TOM API Filter
    target_names = ','.join(map(str, target.names))
    target_response = requests.get(f'{targets_url}?name_fuzzy={target_names}', headers=headers, auth=auth)
    target_response_json = target_response.json()
    try:
        if target_response_json['results']:
            if len(target_response_json['results']) > 1:
                return target_response_json['results'], target_response
            destination_target_id = target_response_json['results'][0]['id']
            return destination_target_id, target_response
        else:
            return None, target_response
    except KeyError:
        return None, target_response


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
    choices = [('download', 'download')]
    try:
        for destination, details in settings.DATA_SHARING.items():
            new_destination = [details.get('DISPLAY_NAME', destination)]
            destination_topics = details.get('USER_TOPICS', [])
            if destination.lower() == 'hermes':
                # If this is a hermes share, get the topics from hermes and override what the users provide
                hermes_topics = get_hermes_topics()
                # If we have no writable hermes topics, then we can't share with hermes!
                if not hermes_topics:
                    destination_topics = []
                elif destination_topics:
                    # If we've set USER_TOPICS with hermes, filter them to those available to your user account
                    destination_topics = [topic for topic in destination_topics if topic in hermes_topics]
                else:
                    destination_topics = hermes_topics
            if destination_topics:
                topic_list = [(f'{destination}:{topic}', topic) for topic in destination_topics]
                new_destination.append(tuple(topic_list))
            else:
                new_destination.insert(0, destination)
            choices.append(tuple(new_destination))
    except AttributeError:
        pass
    return tuple(choices)


def sharing_feedback_handler(response, request):
    """
    Handle the response from a sharing request and prepare a message to the user
    :return:
    """
    try:
        if 'message' in response.json():
            publish_feedback = response.json()['message']
        else:
            publish_feedback = f"ERROR: {response.text}"
    except AttributeError:
        publish_feedback = response['message']
    except ValueError:
        publish_feedback = f"ERROR: Returned Response code {response.status_code}"
    if "ERROR" in publish_feedback.upper():
        messages.error(request, publish_feedback)
    else:
        messages.success(request, publish_feedback)
    return


def download_data(form_data, selected_data):
    """
    Produces a CSV photometry table from the DataShareForm and provides it for download as a StreamingHttpResponse.
    The "title" becomes the filename, and the "message" becomes a comment at the top of the file.
    :param form_data: data from the DataShareForm
    :param selected_data: ReducucedDatums selected via the checkboxes in the DataShareForm
    :return: CSV photometry table as a StreamingHttpResponse
    """
    reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
    serialized_data = [ReducedDatumSerializer(rd).data for rd in reduced_datums]
    for datum in serialized_data:
        datum.update(datum.pop('value'))
    table = Table(serialized_data)
    if form_data.get('share_message'):
        table.meta['comments'] = [form_data['share_message']]
    table.sort('timestamp')
    file_buffer = StringIO()
    ascii.write(table, file_buffer, format='csv', comment='# ')
    file_buffer.seek(0)  # goto the beginning of the buffer
    response = StreamingHttpResponse(file_buffer, content_type="text/ascii")
    filename = slugify(form_data['share_title']) + '.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
