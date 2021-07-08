from django.test import TestCase
from unittest.mock import patch

from tom_alerts.alerts import get_service_class

class TestModuleImport(TestCase):

    def test_import_invalid_mod(self):
        with self.subTest('Test that an invalid import returns an import error.'):
            with patch('tom_observations.api_views.get_service_class') as mock_get_service_class:
                mock_get_service_class.side_effect = ImportError('Import failed. Did you provide the correct path?')
                with self.assertRaises(ImportError):
                    mock_get_service_class()
