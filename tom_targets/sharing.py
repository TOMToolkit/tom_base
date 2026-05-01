"""
Target-level sharing helpers.

Used by ``tom_targets.views.TargetShareView`` and related views, and by the
post-save signal that implements ``PersistentShare`` (continuous sharing).

Dispatch now goes through the SharingBackend registry: parse the
``share_destination`` string's ``<backend_name>:<sub>`` prefix, look up
the backend class with ``tom_common.sharing.get_sharing_backend``, and
call its ``share()`` method. The hardcoded ``if 'HERMES' in destination``
branch was removed during the refactor; HERMES is now just one more
registered backend.

``share_target_with_tom`` (below) is a helper that creates or updates a
Target on a destination TOM; it is separate from ``TomToolkitSharingBackend.share``
because its job is Target registration rather than data sharing.
"""
import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tom_common.sharing import get_destination_target, get_sharing_backend
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.sharing import sharing_feedback_converter
from tom_targets.models import PersistentShare
from tom_targets.serializers import TargetSerializer

logger = logging.getLogger(__name__)


def _parse_backend_name(share_destination: str) -> str:
    """Return the backend name prefix from a ``<backend>:<sub>`` share-destination.

    A missing ':' (legacy TOM-to-TOM form ``'mytom'``) is treated as
    backend ``'tom'``; that keeps old saved PersistentShare values working.
    """
    prefix, sep, _sub = share_destination.partition(':')
    return prefix if sep else 'tom'


def share_target_and_all_data(share_destination, target):
    """Share ``target`` and all of its current DataProducts / ReducedDatums to ``share_destination``.

    Called by ``PersistentShare`` setup when a user first enables
    continuous sharing of a target; we push the one-shot backfill of
    existing data so the destination starts in sync with the source.
    Raises if any step fails so the caller can surface the error.
    """
    backend_name = _parse_backend_name(share_destination)

    if backend_name == 'hermes':
        # HERMES share: push every existing ReducedDatum for this target.
        # The backend filters out any datum already published to this
        # topic via check_for_share_safe_datums.
        datums = ReducedDatum.objects.filter(target=target)
        backend = get_sharing_backend('hermes')()
        tom_name = getattr(settings, 'TOM_NAME', 'TOM Toolkit')
        form_data = {
            'share_destination': share_destination,
            'share_title': f'Setting up continuous sharing for {target.name} from {tom_name}.',
        }
        return sharing_feedback_converter(
            backend.share(form_data, reduced_datums=datums),
        )

    # TOM-to-TOM: first create the Target on the destination TOM (if
    # missing), then push all of its data via the registered backend.
    response = share_target_with_tom(share_destination, {'target': target})
    response_feedback = sharing_feedback_converter(response)
    if 'ERROR' in response_feedback.upper():
        return response_feedback
    backend = get_sharing_backend(backend_name)()
    return sharing_feedback_converter(
        backend.share(
            {'share_destination': share_destination},
            targets=type(target).objects.filter(pk=target.id),
        ),
    )


def continuous_share_data(target, reduced_datums):
    """Push newly-created ``reduced_datums`` to any ``PersistentShare`` destinations for ``target``.

    Triggered from the ``post_save`` signal on ReducedDatum (see
    ``tom_targets.signals``). For each PersistentShare on the target,
    dispatches through the SharingBackend registry.
    """
    persistent_shares = PersistentShare.objects.filter(target=target)
    for persistent_share in persistent_shares:
        share_destination = persistent_share.destination
        reduced_datum_pks = [rd.pk for rd in reduced_datums]
        datums_qs = ReducedDatum.objects.filter(pk__in=reduced_datum_pks)

        backend_name = _parse_backend_name(share_destination)
        tom_name = getattr(settings, 'TOM_NAME', 'TOM Toolkit')
        form_data = {
            'share_destination': share_destination,
            # The share title is used by HERMES for message attribution and
            # is ignored by TomToolkitSharingBackend.
            'share_title': f'Updated data for {target.name} from {tom_name}.',
            'submitter': tom_name,
        }

        try:
            backend = get_sharing_backend(backend_name)()
        except ImportError:
            # Configured destination references a backend that is not
            # installed; log and skip rather than crashing the signal.
            logger.warning(
                'PersistentShare destination %s references unknown backend %s; skipping.',
                share_destination, backend_name,
            )
            continue
        backend.share(form_data, reduced_datums=datums_qs)


def share_target_with_tom(share_destination, form_data, target_lists=()):
    """Create or update a Target on a destination TOM.

    Separate from ``TomToolkitSharingBackend.share`` because this is Target
    registration (``api/targets/``), not data publishing. Called when a
    user first sets up sharing for a target that does not yet exist on the
    destination TOM. Supports both authentication methods
    ``TomToolkitSharingBackend`` supports: DRF API key (``API_KEY``) or
    HTTP Basic (``USERNAME`` / ``PASSWORD``).
    """
    # share_destination may be the legacy bare key ('mytom') or the new
    # prefixed form ('tom:mytom'). Strip the prefix so we can look up the
    # settings.DATA_SHARING entry by its dict key.
    _prefix, _sep, sub = share_destination.partition(':')
    destination_key = sub if _sep else share_destination

    try:
        destination_tom_base_url = settings.DATA_SHARING[destination_key]['BASE_URL']
    except KeyError as err:
        raise ImproperlyConfigured(
            f'Check DATA_SHARING configuration for {destination_key}: Key {err} not found.',
        )

    # Auth: prefer DRF TokenAuth if API_KEY is set; else fall back to HTTP Basic.
    cfg = settings.DATA_SHARING[destination_key]
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    auth = None
    if cfg.get('API_KEY'):
        headers['Authorization'] = f"Token {cfg['API_KEY']}"
    else:
        try:
            auth = (cfg['USERNAME'], cfg['PASSWORD'])
        except KeyError as err:
            raise ImproperlyConfigured(
                f'Check DATA_SHARING configuration for {destination_key}: Key {err} not found. '
                'Provide either API_KEY (preferred) or USERNAME + PASSWORD.',
            )

    targets_url = destination_tom_base_url + 'api/targets/'

    # Resolve whether the target already exists on the destination TOM by
    # fuzzy-matching on its name and aliases.
    destination_target_id, target_search_response = get_destination_target(
        form_data['target'], targets_url, headers, auth,
    )
    if target_search_response.status_code != 200:
        return target_search_response
    if isinstance(destination_target_id, list) and len(destination_target_id) > 1:
        return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}

    # Always tag the created-or-updated target with one TargetList per
    # provided target_list, plus a TargetList named after the source TOM
    # so the destination-TOM operator can see where the target came from.
    target_dict_list = [{'name': f'Imported From {settings.TOM_NAME}'}]
    for target_list in target_lists:
        target_dict_list.append({'name': target_list.name})

    if destination_target_id is None:
        # Target is new on the destination: serialize and create it.
        serialized_target = TargetSerializer(form_data['target']).data
        # Source-TOM group memberships do not translate to the destination;
        # strip them so the destination TOM's permission system starts clean.
        serialized_target['groups'] = []
        serialized_target['target_lists'] = target_dict_list
        target_create_response = requests.post(
            targets_url, json=serialized_target, headers=headers, auth=auth,
        )
    else:
        # Target exists: just append the new target_lists via PATCH.
        update_target_data = {'target_lists': target_dict_list}
        update_target_url = targets_url + f'{destination_target_id}/'
        target_create_response = requests.patch(
            update_target_url, json=update_target_data, headers=headers, auth=auth,
        )
    return target_create_response
