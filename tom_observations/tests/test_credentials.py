"""
Tests for credential management functionality in BaseObservationFacility.

This test module covers:
- CredentialStatus enum
- Credential helper methods in BaseObservationFacility
- Credential validation and fallback logic
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured

from tom_observations.facility import BaseObservationFacility, CredentialStatus


class TestFacility(BaseObservationFacility):
    """Concrete test facility for testing credential management."""
    name = 'TestFacility'

    def get_form(self, observation_type):
        return None

    def submit_observation(self, observation_payload):
        return [1]

    def validate_observation(self, observation_payload):
        return True

    def get_observation_url(self, observation_id):
        return ''

    def get_terminal_observing_states(self):
        return ['COMPLETED', 'FAILED']

    def get_observing_sites(self):
        return {}


class CredentialStatusEnumTests(TestCase):
    """Test the CredentialStatus enum values and behavior."""

    def test_enum_values_exist(self):
        """Test that all expected enum values are defined."""
        self.assertEqual(CredentialStatus.NOT_INITIALIZED.value, "not_initialized")
        self.assertEqual(CredentialStatus.NO_PROFILE.value, "no_profile")
        self.assertEqual(CredentialStatus.PROFILE_EMPTY.value, "profile_empty")
        self.assertEqual(CredentialStatus.USING_DEFAULTS.value, "using_defaults")
        self.assertEqual(CredentialStatus.USING_USER_CREDS.value, "using_user_creds")
        self.assertEqual(CredentialStatus.VALIDATION_FAILED_AUTH.value, "validation_failed_auth")
        self.assertEqual(CredentialStatus.VALIDATION_FAILED_NETWORK.value, "validation_failed_network")

    def test_enum_membership(self):
        """Test that we can check enum membership."""
        self.assertIn(CredentialStatus.NOT_INITIALIZED, CredentialStatus)
        self.assertIn(CredentialStatus.USING_USER_CREDS, CredentialStatus)

    def test_enum_comparison(self):
        """Test that enum values can be compared."""
        status1 = CredentialStatus.USING_USER_CREDS
        status2 = CredentialStatus.USING_USER_CREDS
        status3 = CredentialStatus.USING_DEFAULTS

        self.assertEqual(status1, status2)
        self.assertNotEqual(status1, status3)

    def test_enum_string_representation(self):
        """Test that enum has useful string representation."""
        status = CredentialStatus.USING_USER_CREDS
        self.assertIn("using_user_creds", str(status.value))


class BaseObservationFacilityCredentialTests(TestCase):
    """Test credential-related methods in BaseObservationFacility."""

    def setUp(self):
        """Set up test fixtures."""
        self.facility = TestFacility()
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_initial_credential_status(self):
        """Test that facility starts with NOT_INITIALIZED status."""
        self.assertEqual(self.facility.credential_status, CredentialStatus.NOT_INITIALIZED)

    def test_is_credential_empty_with_none(self):
        """Test that None is recognized as empty credential."""
        self.assertTrue(self.facility._is_credential_empty(None))

    def test_is_credential_empty_with_empty_string(self):
        """Test that empty string is recognized as empty credential."""
        self.assertTrue(self.facility._is_credential_empty(''))
        self.assertTrue(self.facility._is_credential_empty(""))

    def test_is_credential_empty_with_whitespace(self):
        """Test that whitespace-only strings are recognized as empty."""
        self.assertTrue(self.facility._is_credential_empty('   '))
        self.assertTrue(self.facility._is_credential_empty('\t\n'))

    def test_is_credential_empty_with_valid_credential(self):
        """Test that valid credentials are not recognized as empty."""
        self.assertFalse(self.facility._is_credential_empty('valid_username'))
        self.assertFalse(self.facility._is_credential_empty('p@ssw0rd'))

    @override_settings(FACILITIES={
        'TEST_FACILITY': {
            'username': 'default_user',
            'password': 'default_pass'
        }
    })
    def test_get_setting_credentials_success(self):
        """Test successfully getting credentials from settings."""
        creds = self.facility._get_setting_credentials(
            'TEST_FACILITY',
            ['username', 'password']
        )

        self.assertEqual(creds['username'], 'default_user')
        self.assertEqual(creds['password'], 'default_pass')

    @override_settings(FACILITIES={})
    def test_get_setting_credentials_no_facility(self):
        """Test that missing facility in settings raises ImproperlyConfigured."""
        with self.assertRaises(ImproperlyConfigured) as cm:
            self.facility._get_setting_credentials('MISSING_FACILITY', ['username'])

        self.assertIn('MISSING_FACILITY', str(cm.exception))
        self.assertIn('settings.FACILITIES', str(cm.exception))

    @override_settings(FACILITIES={
        'TEST_FACILITY': {
            'username': 'default_user'
            # 'password' is missing
        }
    })
    def test_get_setting_credentials_missing_key(self):
        """Test that missing credential key raises ImproperlyConfigured."""
        with self.assertRaises(ImproperlyConfigured) as cm:
            self.facility._get_setting_credentials(
                'TEST_FACILITY',
                ['username', 'password']
            )

        self.assertIn('password', str(cm.exception))
        self.assertIn('TEST_FACILITY', str(cm.exception))

    def test_raise_no_profile_error(self):
        """Test that _raise_no_profile_error raises with proper message."""
        with self.assertRaises(ImproperlyConfigured) as cm:
            self.facility._raise_no_profile_error(self.user, 'TestFacility')

        exception_message = str(cm.exception)
        self.assertIn('testuser', exception_message)
        self.assertIn('TestFacility', exception_message)
        self.assertIn('Profile', exception_message)

    def test_raise_no_defaults_error(self):
        """Test that _raise_no_defaults_error raises with proper message."""
        with self.assertRaises(ImproperlyConfigured) as cm:
            self.facility._raise_no_defaults_error(self.user, 'TestFacility')

        exception_message = str(cm.exception)
        self.assertIn('testuser', exception_message)
        self.assertIn('TestFacility', exception_message)
        self.assertIn('default credentials', exception_message)
        self.assertIn('settings.FACILITIES', exception_message)
