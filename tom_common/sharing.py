"""
Sharing-backends integration point.

A SharingBackend is a class that publishes TOM data (Targets, DataProducts,
ReducedDatums) to an external destination (e.g., HERMES, another TOM).

### Terminology

- "registry" — in this module, a Python dict that maps each registered
  backend's ``name`` string to the ``SharingBackend`` subclass itself.
  The registry is rebuilt by ``get_sharing_backends()`` on every call.
  We call it a "registry" because callers look a backend up by name and
  get back the class, like looking up a name in a phone book.

### Discovery

Backends are discovered at runtime by iterating installed AppConfigs
(``django.apps.apps.get_app_configs()``) and calling each app's
``sharing_backends()`` method if it has one. This is the same plug-in
mechanism used by ``tom_dataservices.dataservices.get_data_service_classes()``.

### Consumers

``tom_dataproducts.views.DataShareView``, ``tom_dataproducts.forms.DataShareForm``,
and ``tom_targets.sharing`` call ``get_sharing_backend(name)().share(...)``
rather than hardcoding destination-specific branches.

### Included here

- ``TomToolkitSharingBackend`` — publishes to another TOM Toolkit-based TOM
  via its HTTP API. Registered by ``tom_common.apps.TomCommonConfig.sharing_backends()``.

### Registered elsewhere

- ``tom_hermes.sharing.HermesSharingBackend`` — publishes to HERMES.
  Registered by ``tom_hermes.apps.TomHermesConfig.sharing_backends()``.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

import requests
from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.utils.module_loading import import_string

from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.serializers import DataProductSerializer, ReducedDatumSerializer
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class SharingBackend(ABC):
    """Base class (abstract) for a data-sharing destination.

    Each subclass represents one destination family: one class for HERMES,
    one for TOM-to-TOM, and so on. Instances are short-lived and created
    per ``share()`` invocation by the consumer code.
    """

    # ``name`` is:
    #   - the key in the dict returned by ``get_sharing_backends()``;
    #   - used as the prefix of the form's ``share_destination`` value, which is
    #     formatted as the string ``'<name>:<sub-destination>'``
    #     (e.g. ``'hermes:gw.lvk.public'``, or ``'tom:tom_b'``);
    #   - the value that ``DataShareView.post()`` parses out of
    #     ``share_destination`` to look up this backend's class and
    #     dispatch to its ``share()`` method.
    # Required: set to a short, unique, machine-readable string in every subclass.
    name: str = ''

    # ``verbose_name`` is the human-readable label shown as the heading above
    # this backend's destinations in the share-destination dropdown.
    # Required: set in every subclass.
    verbose_name: str = ''

    @classmethod
    def get_destination_choices(cls, user: User | None = None) -> list:
        """Return the (value, label) pairs that populate this backend's options in the share-destination dropdown.

        Called by ``DataShareForm.__init__`` at form-render time. Each
        returned ``value`` is a string formatted as
        ``'<cls.name>:<sub-destination>'`` so ``DataShareView.post()`` can
        parse the prefix and look up this class in the registry. The
        returned ``label`` is what the user sees.

        Implementations typically call the destination (e.g., to list
        topics), or read ``settings.DATA_SHARING``, to enumerate configured
        sub-destinations.
        """
        raise NotImplementedError

    @abstractmethod
    def share(self, form_data: dict, *,
              reduced_datums: QuerySet | None = None,
              targets: QuerySet | None = None,
              data_products: QuerySet | None = None,
              user: User | None = None,
              **kwargs) -> dict:
        """Execute the share operation.

        Called by ``DataShareView.post()`` (and by the shims in
        ``tom_dataproducts.sharing``) after a successful form submission.

        Returns a feedback dict with at least
        ``{'status': 'success'|'error', 'message': str}`` (older code
        returns just ``{'message': str}``; both are tolerated by the
        sharing feedback handler).
        """

    def validate_credentials(self, user: User | None = None) -> bool:
        """Check that the user has credentials configured for this backend.

        Called by ``DataShareForm.clean()`` when the form is about to
        submit. Default returns True (the backend needs no per-user
        credentials). Subclasses override to check e.g. that a
        ``HermesProfile`` API key is set for the current user.
        """
        return True


def get_sharing_backends() -> dict:
    """Build and return the registry of all SharingBackend subclasses registered by installed apps.

    The registry is a dict that maps each backend's ``name`` string to the
    ``SharingBackend`` subclass itself. It is rebuilt on every call so
    tests that patch installed apps see the patched state.

    How it is built:

    1. Iterate ``django_apps.get_app_configs()``.
    2. For each AppConfig that has a ``sharing_backends()`` method, call it.
       The method returns a list of dicts of the form
       ``[{'class': dotted_path}, ...]``.
    3. Import each class by its dotted path. Each class's ``name`` attribute
       becomes the registry key.

    AppConfigs without the method are skipped (``AttributeError`` is
    caught). Import failures are logged and the offending entry is
    skipped, so one broken backend does not prevent the others from being
    registered.
    """
    # Dict keyed by SharingBackend.name; value is the SharingBackend subclass itself.
    registry: dict = {}
    for app in django_apps.get_app_configs():
        try:
            entries = app.sharing_backends()
        except AttributeError:
            # This AppConfig does not declare the integration point; that is fine.
            continue
        for entry in entries or []:
            try:
                clazz = import_string(entry['class'])
            except ImportError as exc:
                logger.warning('Could not import SharingBackend %s for %s: %s',
                               entry.get('class'), app.name, exc)
                continue
            registry[clazz.name] = clazz
    return registry


def get_sharing_backend(name: str) -> type:
    """Look up one SharingBackend class by its ``name`` attribute.

    Builds the registry via ``get_sharing_backends()`` and does a dict
    lookup. Raises ``ImportError`` with a message that tells the user
    how to fix the missing backend (install the providing app). Uses the
    same structure as
    ``tom_dataservices.dataservices.get_data_service_class`` so the
    behavior is consistent across integration points.
    """
    # build the registry
    registry = get_sharing_backends()
    try:
        # look up the given SharingBackend by name
        return registry[name]
    except KeyError:
        raise ImportError(
            f"Could not find a SharingBackend named '{name}'. "
            f"Did you install the app that provides it, and add it to INSTALLED_APPS?"
        )


class TomToolkitSharingBackend(SharingBackend):
    """SharingBackend for publishing to another TOM Toolkit-based TOM.

    Destinations come from ``settings.DATA_SHARING``. Each entry whose
    value dict has ``BASE_URL`` and does NOT have ``HERMES_API_KEY`` is
    treated as a TOM destination. (HERMES entries are identified by the
    presence of ``HERMES_API_KEY`` and are handled by
    ``HermesSharingBackend`` in the ``tom_hermes`` app.)

    Authentication supports two methods, chosen per destination by what
    the TOM operator puts in ``settings.DATA_SHARING[<name>]``:

    - ``API_KEY`` set — uses ``Authorization: Token <api_key>`` (DRF
      TokenAuth). Preferred: TOM Toolkit auto-generates a DRF token per
      user, and the destination TOM's operator can create a
      service-account token to share.
    - Otherwise — uses HTTP Basic with ``USERNAME`` and ``PASSWORD``
      (existing method, kept for continuity).

    Example ``settings.DATA_SHARING`` supporting multiple TOM destinations
    plus HERMES::

        DATA_SHARING = {
            # TOM destinations (picked up by TomToolkitSharingBackend):
            'tom_a': {
                'DISPLAY_NAME': 'TOM A',
                'BASE_URL':     'https://tom-a.example.org/',
                'API_KEY':      'drf-token-string',   # preferred; Token auth
            },
            'tom_b': {
                'DISPLAY_NAME': 'TOM B',
                'BASE_URL':     'https://tom-b.example.org/',
                'USERNAME':     'alice',              # fallback: Basic auth
                'PASSWORD':     's3cret',
            },
            # HERMES destination (picked up by HermesSharingBackend):
            'hermes': {
                'BASE_URL':       'https://hermes.lco.global/',
                'HERMES_API_KEY': 'hermes-api-key',
            },
        }
    """

    # ``name = 'tom'`` because the share-destination form field encodes a
    # choice from this backend as ``'tom:<tom_destination_name>'``.
    # ``DataShareView.post()`` parses the ``'tom'`` prefix and looks up
    # this class in the registry.
    name = 'tom'

    # ``verbose_name = 'Another TOM'`` is the heading shown above this
    # backend's destinations in the share-destination dropdown.
    verbose_name = 'Another TOM'

    @classmethod
    def get_destination_choices(cls, user: User | None = None) -> list:
        """Enumerate ``settings.DATA_SHARING`` entries that look like TOM destinations and
        return list of tuples to populate ChoiceField choices.

        A "TOM destination" entry is one whose value dict has a
        ``BASE_URL`` and does NOT have a ``HERMES_API_KEY``. Each such
        entry becomes one dropdown option formatted as
        ``('tom:<key>', cfg.get('DISPLAY_NAME', key))``.

        Returns an empty list if ``settings.DATA_SHARING`` is not set or
        contains no TOM-shaped entries.
        """
        choices: list = []
        data_sharing = getattr(settings, 'DATA_SHARING', {}) or {}
        for key, cfg in data_sharing.items():
            # Skip HERMES entries; they belong to HermesSharingBackend.
            if not isinstance(cfg, dict) or cfg.get('HERMES_API_KEY'):
                continue
            display_name = cfg.get('DISPLAY_NAME', key)
            if not cfg.get('BASE_URL'):
                # Not enough info to publish — skip quietly rather than erroring
                # at form-render time.
                logger.warning(f'No BASE_URL found in DATA_SHARING config for {display_name}')
                continue
            choices.append((f'{cls.name}:{key}', display_name))
        return choices

    @staticmethod
    def _split_destination(share_destination: str) -> str:
        """Return the ``<sub-destination>`` half of a ``'tom:<sub>'`` share-destination string.
        """
        prefix, sep, sub = share_destination.partition(':')
        if sep:
            return sub
        return prefix

    @staticmethod
    def _build_auth(cfg: dict):
        """Return a ``(headers_update, auth_tuple_or_None)`` pair for ``requests``.

        Prefers DRF TokenAuth if ``API_KEY`` is set in the settings entry;
        otherwise falls back to HTTP Basic with ``USERNAME`` / ``PASSWORD``.
        ``headers_update`` is a dict to merge into the base request headers;
        ``auth_tuple_or_None`` is the ``auth=`` argument for ``requests``.
        """
        api_key = cfg.get('API_KEY')
        if api_key:
            # DRF TokenAuthentication expects the literal word "Token" (not "Bearer").
            return {'Authorization': f'Token {api_key}'}, None
        username = cfg.get('USERNAME')
        password = cfg.get('PASSWORD')
        if username is not None and password is not None:
            return {}, (username, password)
        # Nothing configured — let the destination TOM reject the request;
        # that produces a clearer error than raising here.
        return {}, None

    def share(self, form_data: dict, *,
              reduced_datums: QuerySet | None = None,
              targets: QuerySet | None = None,
              data_products: QuerySet | None = None,
              user: User | None = None,
              **kwargs) -> dict:
        """POST the share payload to the destination TOM's HTTP API.

        Authentication now prefers a DRF API token if
        ``settings.DATA_SHARING[<dest>]['API_KEY']`` is set, falling back to
        HTTP Basic if only ``USERNAME`` / ``PASSWORD`` are configured.

        The caller passes whichever of ``reduced_datums`` / ``targets`` /
        ``data_products`` is relevant to the share action; the three are
        mutually-exclusive in practice.
        """
        # Parse the destination sub-key out of the form value (e.g. 'tom:tom_b' -> 'tom_b').
        share_destination = form_data.get('share_destination', '') if form_data else ''
        destination_key = self._split_destination(share_destination)

        # Look up the destination's settings entry. If it's missing or
        # malformed, return an error-shaped feedback dict rather than
        # raising, so the view can surface it to the user via the messages
        # framework.
        data_sharing = getattr(settings, 'DATA_SHARING', {}) or {}
        try:
            cfg = data_sharing[destination_key]
            destination_tom_base_url = cfg['BASE_URL']
        except KeyError as err:
            return {'message': (
                f'ERROR: Check DATA_SHARING configuration for '
                f"'{destination_key}': key {err} not found."
            )}

        # Build the base headers and the appropriate auth. Auth is chosen
        # per-destination: API_KEY take precedence over USERNAME/PASSWORD.
        base_headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        auth_headers, auth = self._build_auth(cfg)
        headers = {**base_headers, **auth_headers}

        # Destination endpoints on the receiving TOM.
        dataproducts_url = destination_tom_base_url + 'api/dataproducts/'
        targets_url = destination_tom_base_url + 'api/targets/'
        reduced_datums_url = destination_tom_base_url + 'api/reduceddatums/'

        # Dispatch on which of the three querysets was supplied:
        # ``data_products`` / ``reduced_datums`` / ``targets``
        if data_products is not None and data_products.exists():
            return self._share_data_products(
                data_products, targets_url, dataproducts_url, headers, auth,
            )
        if reduced_datums is not None and reduced_datums.exists():
            return self._share_reduced_datums(
                reduced_datums, targets_url, reduced_datums_url, headers, auth, destination_key,
            )
        if targets is not None and targets.exists():
            # A Target-only share: push every ReducedDatum that belongs to
            # the target. We do NOT create the Target on the destination
            # TOM — that target must already exist there.
            target = targets.first()
            owned_datums = ReducedDatum.objects.filter(target=target)
            return self._share_reduced_datums(
                owned_datums, targets_url, reduced_datums_url, headers, auth, destination_key,
            )
        return {'message': 'ERROR: No valid data to share.'}

    @staticmethod
    def _share_data_products(data_products: QuerySet, targets_url: str, dataproducts_url: str,
                             headers: dict, auth) -> dict:
        """Upload each DataProduct file to the destination TOM.

        Finds a matching Target on the destination by fuzzy-matching on
        target names and aliases (``get_destination_target``), then POSTs
        the serialized DataProduct plus its file to ``api/dataproducts/``.
        """
        # We currently support one DataProduct per call.
        # If there are multiple, only the first is processed; others are ignored.
        product = data_products.first()
        target = product.target
        serialized_data = DataProductSerializer(product).data

        destination_target_id, _ = get_destination_target(target, targets_url, headers, auth)
        if destination_target_id is None:
            return {'message': 'ERROR: No matching target found.'}
        if isinstance(destination_target_id, list) and len(destination_target_id) > 1:
            return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}
        serialized_data['target'] = destination_target_id

        # TODO: this path join should be replaced once tom_dataproducts uses
        # django.core.files.storage
        dataproduct_filename = os.path.join(settings.MEDIA_ROOT, product.data.name)
        with open(dataproduct_filename, 'rb') as dataproduct_filep:
            files = {'file': (product.data.name, dataproduct_filep, 'text/csv')}
            # For multipart/form-data, requests sets the Content-Type header
            # itself; override the JSON content-type we set above. Auth header
            # (if any) flows through unchanged.
            upload_headers = {k: v for k, v in headers.items() if k != 'Content-Type'}
            upload_headers['Media-Type'] = 'multipart/form-data'
            response = requests.post(dataproducts_url, data=serialized_data, files=files,
                                     headers=upload_headers, auth=auth)
        return response

    @staticmethod
    def _share_reduced_datums(reduced_datums: QuerySet, targets_url: str, reduced_datums_url: str,
                              headers: dict, auth, destination_key: str) -> dict:
        """POST each ReducedDatum to the destination TOM.

        Resolves each datum's Target on the destination TOM (by fuzzy
        name match), then POSTs the serialized datum to
        ``api/reduceddatums/``. Returns a summary message with the number
        of datums saved.
        """
        # First resolve every source Target to its destination-TOM id.
        targets_set = {reduced_datum.target for reduced_datum in reduced_datums}
        target_dict: dict = {}
        for target in targets_set:
            destination_target_id, _ = get_destination_target(target, targets_url, headers, auth)
            if isinstance(destination_target_id, list) and len(destination_target_id) > 1:
                return {'message': 'ERROR: Multiple targets with matching name found in destination TOM.'}
            target_dict[target.name] = destination_target_id
        if all(value is None for value in target_dict.values()):
            return {'message': 'ERROR: No matching target found.'}

        # Run datums through the existing sharing-protocol filter so a
        # datum already published to this destination is not re-sent.
        from tom_dataproducts.sharing import check_for_share_safe_datums
        reduced_datums = check_for_share_safe_datums(destination_key, reduced_datums)
        if not reduced_datums:
            return {'message': 'ERROR: No valid data to share.'}

        response_codes: list = []
        for datum in reduced_datums:
            if not target_dict.get(datum.target.name):
                continue
            serialized_data = ReducedDatumSerializer(datum).data
            serialized_data['target'] = target_dict[datum.target.name]
            serialized_data['data_product'] = ''
            # Stamp provenance on the outgoing datum if the source did not
            # already provide it, so the destination TOM can trace where
            # the datum came from.
            if not serialized_data.get('source_name'):
                serialized_data['source_name'] = settings.TOM_NAME
                serialized_data['source_location'] = (
                    f"ReducedDatum shared from <{settings.TOM_NAME}.url>"
                    f"/api/reduceddatums/{datum.id}/"
                )
            response = requests.post(reduced_datums_url, json=serialized_data,
                                     headers=headers, auth=auth)
            response_codes.append(response.status_code)

        failed_count = len([rc for rc in response_codes if rc >= 300])
        if failed_count < len(response_codes):
            saved = len(response_codes) - failed_count
            return {'message': f'{saved} of {len(response_codes)} datums successfully saved.'}
        return {'message': 'ERROR: No valid data shared. These data may already exist in target TOM.'}


def get_destination_target(target: Target, targets_url: str, headers: dict, auth) -> tuple:
    """Find the destination-TOM target id that matches the given source target.

    Uses the destination TOM's ``api/targets/?name_fuzzy=`` filter with a
    comma-separated list of the source target's name and aliases. Returns
    ``(id_or_list_or_None, http_response)``:

    - A single matched id if exactly one destination target matches.
    - The full list of result dicts if more than one matched (caller can
      decide which one to use, or surface an error).
    - ``None`` if no target matches.

    Moved here from ``tom_dataproducts.sharing`` so that TomToolkitSharingBackend
    and future TOM-to-TOM utilities can share one implementation.
    """
    # Build a comma-separated list of target names plus aliases that the
    # TOM API name_fuzzy filter will parse.
    target_names = ','.join(map(str, target.names))
    target_response = requests.get(f'{targets_url}?name_fuzzy={target_names}',
                                   headers=headers, auth=auth)
    target_response_json = target_response.json()
    try:
        if target_response_json['results']:
            if len(target_response_json['results']) > 1:
                return target_response_json['results'], target_response
            destination_target_id = target_response_json['results'][0]['id']
            return destination_target_id, target_response
        return None, target_response
    except KeyError:
        return None, target_response
