"""
Tests for the ``sharing_backends`` integration point in ``tom_common.sharing``.

These tests must pass with ``tom_hermes`` NOT installed — the discovery
mechanism is supposed to work without any particular third-party
SharingBackend being available. A test-only fake ``SharingBackend``
subclass declared below stands in for HERMES / other real backends.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from tom_common.sharing import (
    SharingBackend,
    TomToolkitSharingBackend,
    get_sharing_backend,
    get_sharing_backends,
)


class _FakeSharingBackend(SharingBackend):
    """Test-only backend. Declared at module scope so ``import_string`` can resolve it."""

    name = 'fake'
    verbose_name = 'Fake'

    @classmethod
    def get_destination_choices(cls, user=None):
        return [('fake:one', 'one'), ('fake:two', 'two')]

    def share(self, form_data, **kwargs):
        # Returns a feedback dict shaped like the real backends do on success.
        return {'status': 'success', 'message': 'ok'}


class _FakeAppConfig:
    """Minimal AppConfig stand-in used to register ``_FakeSharingBackend``.

    ``get_sharing_backends`` reads each installed AppConfig's
    ``sharing_backends()`` method, imports the listed class paths, and
    keys them by class ``name``. To simulate a registered backend we
    inject this AppConfig into ``apps.get_app_configs()`` via patch.
    """

    name = 'fake_app'

    def sharing_backends(self):
        return [{'class': 'tom_common.test_sharing._FakeSharingBackend'}]


class SharingRegistryTests(TestCase):
    """Verify the registry discovery / lookup helpers."""

    def test_get_sharing_backends_includes_fake_from_patched_appconfig(self):
        # ``get_sharing_backends`` iterates ``apps.get_app_configs()``.
        # Patching it to return a single fake AppConfig lets us assert
        # the discovery path without relying on any real third-party
        # SharingBackend being installed.
        with patch('tom_common.sharing.django_apps.get_app_configs',
                   return_value=[_FakeAppConfig()]):
            registry = get_sharing_backends()
        self.assertIn('fake', registry)
        self.assertIs(registry['fake'], _FakeSharingBackend)

    def test_get_sharing_backends_skips_appconfig_without_method(self):
        # An AppConfig without ``sharing_backends()`` must be silently
        # skipped (the hook is optional).
        appconfig_no_hook = MagicMock(spec=['name'])
        appconfig_no_hook.name = 'no_hook'
        del appconfig_no_hook.sharing_backends  # make AttributeError real
        with patch('tom_common.sharing.django_apps.get_app_configs',
                   return_value=[appconfig_no_hook, _FakeAppConfig()]):
            registry = get_sharing_backends()
        self.assertEqual(list(registry), ['fake'])

    def test_get_sharing_backends_skips_unresolvable_class_path(self):
        # When a class path fails to import, the offending entry is
        # skipped — one broken backend must not prevent the others
        # from being registered.
        class BadAppConfig:
            name = 'bad_app'

            def sharing_backends(self_inner):
                return [{'class': 'nonexistent.module.DoesNotExist'}]

        with patch('tom_common.sharing.django_apps.get_app_configs',
                   return_value=[BadAppConfig(), _FakeAppConfig()]):
            registry = get_sharing_backends()
        self.assertEqual(list(registry), ['fake'])

    def test_get_sharing_backend_returns_class_by_name(self):
        with patch('tom_common.sharing.django_apps.get_app_configs',
                   return_value=[_FakeAppConfig()]):
            self.assertIs(get_sharing_backend('fake'), _FakeSharingBackend)

    def test_get_sharing_backend_raises_import_error_when_missing(self):
        # Unknown names raise ImportError with a message that names the
        # fix — the caller should see "install the app that provides it".
        with patch('tom_common.sharing.django_apps.get_app_configs',
                   return_value=[_FakeAppConfig()]):
            with self.assertRaises(ImportError) as ctx:
                get_sharing_backend('no-such-backend')
        self.assertIn('INSTALLED_APPS', str(ctx.exception))


class TomToolkitSharingBackendChoicesTests(TestCase):
    """Verify that destination-dropdown choices come from ``settings.DATA_SHARING``."""

    @override_settings(DATA_SHARING={
        'tom_a': {'DISPLAY_NAME': 'TOM A', 'BASE_URL': 'https://a.example/'},
        'tom_b': {'DISPLAY_NAME': 'TOM B', 'BASE_URL': 'https://b.example/'},
        # HERMES-shaped entry is recognized by HERMES_API_KEY and should NOT
        # appear under TomToolkitSharingBackend's choices.
        'hermes': {'BASE_URL': 'https://hermes.example/', 'HERMES_API_KEY': 'x'},
        # Missing BASE_URL is skipped quietly rather than erroring at render.
        'broken': {'DISPLAY_NAME': 'Broken'},
    })
    def test_choices_include_tom_entries_and_exclude_hermes(self):
        choices = TomToolkitSharingBackend.get_destination_choices(user=None)
        # Ordering matches dict insertion order.
        self.assertEqual(choices, [
            ('tom:tom_a', 'TOM A'),
            ('tom:tom_b', 'TOM B'),
        ])

    @override_settings(DATA_SHARING={})
    def test_choices_empty_when_no_settings(self):
        self.assertEqual(TomToolkitSharingBackend.get_destination_choices(user=None), [])


class TomToolkitSharingBackendAuthTests(TestCase):
    """Verify that _build_auth picks API_KEY over USERNAME/PASSWORD."""

    def test_api_key_produces_token_auth_header(self):
        cfg = {'API_KEY': 'abc123', 'USERNAME': 'u', 'PASSWORD': 'p'}
        headers, auth = TomToolkitSharingBackend._build_auth(cfg)
        # API_KEY wins even when USERNAME/PASSWORD are also set.
        self.assertEqual(headers, {'Authorization': 'Token abc123'})
        self.assertIsNone(auth)

    def test_username_password_produces_basic_auth_tuple(self):
        cfg = {'USERNAME': 'alice', 'PASSWORD': 'secret'}
        headers, auth = TomToolkitSharingBackend._build_auth(cfg)
        self.assertEqual(headers, {})
        self.assertEqual(auth, ('alice', 'secret'))

    def test_no_credentials_returns_empty(self):
        # When neither API_KEY nor USERNAME/PASSWORD are set, we return
        # empty auth and let the destination TOM reject the request —
        # that produces a clearer error than raising here.
        headers, auth = TomToolkitSharingBackend._build_auth({})
        self.assertEqual(headers, {})
        self.assertIsNone(auth)


class TomToolkitSharingBackendSplitDestinationTests(TestCase):
    """Verify the parser that extracts the sub-destination from ``<prefix>:<sub>``."""

    def test_prefixed_form(self):
        self.assertEqual(
            TomToolkitSharingBackend._split_destination('tom:tom_b'),
            'tom_b',
        )

    def test_legacy_bare_form(self):
        # Legacy callers still pass the bare settings key without the prefix.
        # _split_destination must tolerate that and return the whole string.
        self.assertEqual(
            TomToolkitSharingBackend._split_destination('mytom'),
            'mytom',
        )
