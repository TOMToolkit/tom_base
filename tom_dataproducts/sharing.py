"""
Data-sharing helpers retained in tom_dataproducts.

The SharingBackend framework and the bundled ``TomToolkitSharingBackend``
(share with another TOM) live in ``tom_common.sharing``. HERMES-specific
code lives in ``tom_hermes``. This module retains:

- ``get_sharing_destination_options`` — iterates every registered
  SharingBackend and collects its ``get_destination_choices(user)`` output
  for the share-destination dropdown.
- ``check_for_share_safe_datums`` — generic filter that drops ReducedDatums
  already published to the destination topic. Used by
  ``HermesSharingBackend.share`` (lazy import).
- Sharing feedback helpers (``sharing_feedback_converter``,
  ``sharing_feedback_handler``).
- CSV download helpers (``process_spectro_data_for_download``,
  ``download_data``) — the "download" sharing destination.
- ``get_destination_target`` — re-exported from ``tom_common.sharing`` so
  existing ``tom_targets.sharing`` imports keep working.
"""
from io import StringIO

from astropy.io import ascii
from astropy.table import Table
from django.contrib import messages
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils.text import slugify

# get_destination_target is re-exported here so existing tom_targets.sharing
# imports keep working after its move into tom_common.sharing.
from tom_common.sharing import get_destination_target  # noqa: F401
from tom_common.sharing import get_sharing_backends
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.serializers import ReducedDatumSerializer


# ---------------------------------------------------------------------------
# Sharing-destination dropdown: iterate the SharingBackend registry
# ---------------------------------------------------------------------------

def get_sharing_destination_options(include_download=True, user=None):
    """Build the choices tuple for ``DataShareForm.share_destination``.

    Called by ``DataShareForm.__init__``. Iterates every SharingBackend
    registered via the ``sharing_backends()`` AppConfig integration point
    and collects each backend's ``get_destination_choices(user)``. Each
    backend's options are grouped under its ``verbose_name`` heading in
    the dropdown.

    The optional ``download`` entry (not a backend — emits a CSV to the
    user directly) is still handled as a hardcoded first option.
    """
    choices = []
    if include_download:
        choices.append(('download', 'download'))

    for backend_cls in get_sharing_backends().values():
        backend_choices = list(backend_cls.get_destination_choices(user=user))
        if not backend_choices:
            continue
        # Django select widgets render a tuple ``(group_label, tuple_of_choices)``
        # as an optgroup. Wrap this backend's choices in that shape so
        # they appear under the backend's verbose_name heading.
        choices.append((backend_cls.verbose_name, tuple(backend_choices)))

    return tuple(choices)


# ---------------------------------------------------------------------------
# Generic share helpers
# ---------------------------------------------------------------------------

def check_for_share_safe_datums(destination, reduced_datums, **kwargs):
    """Drop ReducedDatums that have already been published to the given destination+topic.

    Generic hook — subclassable / replaceable by a TOM operator for a
    different selection experience. Today has one built-in rule: for
    HERMES, exclude datums already linked to an ``AlertStreamMessage``
    with ``exchange_status='published'`` on the same topic. For other
    destinations, it is a no-op.

    Called by ``HermesSharingBackend.share`` (lazy import) and by
    ``TomToolkitSharingBackend.share`` (lazy import).
    """
    if 'hermes' in destination:
        message_topic = kwargs.get('topic', None)
        filtered_datums = reduced_datums.exclude(
            Q(message__exchange_status='published') & Q(message__topic=message_topic),
        )
    else:
        filtered_datums = reduced_datums
    return filtered_datums


def sharing_feedback_converter(response):
    """Extract a human-readable message from a sharing response object.

    Tolerant of three shapes that the share functions return:

    - A ``requests.Response`` object: extract ``.json()['message']`` if
      present, else a generic "Submitted message succesfully".
    - A feedback dict (``{'message': str}``): return the message directly.
    - Anything that raises — render the status code and content.
    """
    try:
        response.raise_for_status()
        if 'message' in response.json():
            feedback_message = response.json()['message']
        else:
            feedback_message = 'Submitted message succesfully'
    except AttributeError:
        # response is a plain dict (from the share_* shims in error cases).
        feedback_message = response['message']
    except Exception:
        feedback_message = (
            f'ERROR: Returned Response code {response.status_code} '
            f'with content: {response.content}'
        )
    return feedback_message


def sharing_feedback_handler(response, request):
    """Push a sharing response's feedback into Django's messages framework.

    ERROR-shaped feedback becomes a ``messages.error``; anything else
    becomes ``messages.success``. Called from every view that runs a
    share operation.
    """
    publish_feedback = sharing_feedback_converter(response)
    if 'ERROR' in publish_feedback.upper():
        messages.error(request, publish_feedback)
    else:
        messages.success(request, publish_feedback)
    return


# ---------------------------------------------------------------------------
# CSV download (the "download" sharing destination)
# ---------------------------------------------------------------------------

def process_spectro_data_for_download(serialized_datum):
    """Expand a serialized spectroscopy ReducedDatum into one row per flux/wavelength pair.

    Used by ``download_data`` so a spectroscopy ReducedDatum (which
    carries parallel flux/wavelength arrays in its ``value`` dict)
    becomes multiple rows in the downloaded CSV. Also handles the
    legacy "dict of rows" shape.
    """
    download_datums = []
    spectra_data = serialized_datum.pop('value')
    if ('flux' in spectra_data and isinstance(spectra_data['flux'], list)
            and 'wavelength' in spectra_data and isinstance(spectra_data['wavelength'], list)
            and len(spectra_data['flux']) == len(spectra_data['wavelength'])):
        datum_to_copy = serialized_datum.copy()
        # Copy scalar (non-array, non-dict) fields through to the per-row
        # copies so they appear on every expanded row.
        for key, value in spectra_data.items():
            if not isinstance(value, (list, dict)) and key not in datum_to_copy:
                datum_to_copy[key] = value
        for i, flux in enumerate(spectra_data['flux']):
            expanded_datum = datum_to_copy.copy()
            expanded_datum['flux'] = flux
            expanded_datum['wavelength'] = spectra_data['wavelength'][i]
            if 'flux_error' in spectra_data and isinstance(spectra_data['flux_error'], list):
                expanded_datum['flux_error'] = spectra_data['flux_error'][i]
            download_datums.append(expanded_datum)
    else:
        # Legacy "dict of rows" shape: each value is itself a row dict.
        for entry in spectra_data.values():
            if isinstance(entry, dict):
                expanded_datum = serialized_datum.copy()
                expanded_datum.update(entry)
                download_datums.append(expanded_datum)
    return download_datums


def download_data(form_data, selected_data):
    """Produce a CSV photometry/spectroscopy table as a ``StreamingHttpResponse``.

    The share-destination ``'download'`` dispatches here (see
    ``DataShareView.post``). The form's ``share_title`` becomes the CSV
    filename; ``share_message`` becomes a top-of-file comment line.
    """
    reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
    serialized_data = [ReducedDatumSerializer(rd).data for rd in reduced_datums]
    data_to_save = []
    sort_fields = ['timestamp']
    for datum in serialized_data:
        if datum.get('data_type') == 'photometry':
            # Flatten the photometry value dict into the datum row.
            datum.update(datum.pop('value'))
            data_to_save.append(datum)
        elif datum.get('data_type') == 'spectroscopy':
            sort_fields = ['timestamp', 'wavelength']
            data_to_save.extend(process_spectro_data_for_download(datum))
    table = Table(data_to_save)
    if form_data.get('share_message'):
        table.meta['comments'] = [form_data['share_message']]
    table.sort(sort_fields)
    file_buffer = StringIO()
    ascii.write(table, file_buffer, format='csv', comment='# ')
    file_buffer.seek(0)
    response = StreamingHttpResponse(file_buffer, content_type='text/ascii')
    filename = slugify(form_data['share_title']) + '.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
