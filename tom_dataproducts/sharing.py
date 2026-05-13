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
from tom_dataproducts.serializers import DataProductSerializer, ReducedDatumSerializer


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
    :param destination: sharing destination string
    :param reduced_datums: selected input datums
    :return: queryset of reduced datums to be shared
    """
    filtered_datums = reduced_datums
    return filtered_datums


def check_for_save_safe_datums():
    return


def get_sharing_destination_options(include_download=True):
    """
    Build the Display options and headers for the dropdown form for choosing sharing topics.
    Customize for a different selection experience.
    :return: Tuple: Possible Destinations and their Display Names
    """
    if include_download:
        choices = [('download', 'download')]
    else:
        choices = []
    try:
        for destination, details in settings.DATA_SHARING.items():
            new_destination = [details.get('DISPLAY_NAME', destination)]
            destination_topics = details.get('USER_TOPICS', [])
            if destination_topics:
                topic_list = [(f'{destination}:{topic}', topic) for topic in destination_topics]
                new_destination.append(tuple(topic_list))
            else:
                new_destination.insert(0, destination)
            choices.append(tuple(new_destination))
    except AttributeError:
        pass
    return tuple(choices)


def sharing_feedback_converter(response):
    """
    Takes a sharing feedback response and returns its error or success message
    """
    try:
        response.raise_for_status()
        if 'message' in response.json():
            feedback_message = response.json()['message']
        else:
            feedback_message = "Submitted message succesfully"
    except AttributeError:
        feedback_message = response['message']
    except Exception:
        feedback_message = f"ERROR: Returned Response code {response.status_code} with content: {response.content}"

    return feedback_message


def sharing_feedback_handler(response, request):
    """
    Handle the response from a sharing request and prepare a message to the user
    :return:
    """
    publish_feedback = sharing_feedback_converter(response)
    if "ERROR" in publish_feedback.upper():
        messages.error(request, publish_feedback)
    else:
        messages.success(request, publish_feedback)
    return


def process_spectro_data_for_download(serialized_datum):
    """ Turns a serialized spectrograph datum into a list of serialized datums with the
        spectrograph info expanded one piece per line
    """
    download_datums = []
    spectra_data = serialized_datum.pop('value')
    if ('flux' in spectra_data and isinstance(spectra_data['flux'], list)
        and 'wavelength' in spectra_data and isinstance(spectra_data['wavelength'], list)
            and len(spectra_data['flux']) == len(spectra_data['wavelength'])):
        datum_to_copy = serialized_datum.copy()
        # If its a data dict with certain array or dict fields, then first copy the scalar fields over
        for key, value in spectra_data.items():
            if not isinstance(value, (list, dict)) and key not in datum_to_copy:
                datum_to_copy[key] = value
        # And then iterate over the expected array fields to build output rows
        for i, flux in enumerate(spectra_data['flux']):
            expanded_datum = datum_to_copy.copy()
            expanded_datum['flux'] = flux
            expanded_datum['wavelength'] = spectra_data['wavelength'][i]
            if 'flux_error' in spectra_data and isinstance(spectra_data['flux_error'], list):
                expanded_datum['flux_error'] = spectra_data['flux_error'][i]
            download_datums.append(expanded_datum)
    else:
        for entry in spectra_data.values():
            if isinstance(entry, dict):
                expanded_datum = serialized_datum.copy()
                # If its an "array" of dicts, just expand each dict into the output
                expanded_datum.update(entry)
                download_datums.append(expanded_datum)
    return download_datums


def download_data(form_data, selected_data):
    """
    Produces a CSV photometry or spectroscopy table from the DataShareForm and provides it for download
    as a StreamingHttpResponse.
    The "title" becomes the filename, and the "message" becomes a comment at the top of the file.
    :param form_data: data from the DataShareForm
    :param selected_data: ReducucedDatums selected via the checkboxes in the DataShareForm
    :return: CSV photometry or spectroscopy table as a StreamingHttpResponse
    """
    reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
    serialized_data = [ReducedDatumSerializer(rd).data for rd in reduced_datums]
    data_to_save = []
    sort_fields = ['timestamp']
    for datum in serialized_data:
        if datum.get('data_type') == 'photometry':
            datum.update(datum.pop('value'))
            data_to_save.append(datum)
        elif datum.get('data_type') == 'spectroscopy':
            sort_fields = ['timestamp', 'wavelength']
            # Attempt to expand the photometry table stored in the .value into multiple entries in serialized data
            data_to_save.extend(process_spectro_data_for_download(datum))
    table = Table(data_to_save)
    if form_data.get('share_message'):
        table.meta['comments'] = [form_data['share_message']]
    table.sort(sort_fields)
    file_buffer = StringIO()
    ascii.write(table, file_buffer, format='csv', comment='# ')
    file_buffer.seek(0)  # goto the beginning of the buffer
    response = StreamingHttpResponse(file_buffer, content_type="text/ascii")
    filename = slugify(form_data['share_title']) + '.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
