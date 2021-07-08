from django.test import TestCase
from unittest.mock import patch

from tom_alerts.alerts import get_service_classes

class TestModuleImport(TestCase):

    def test_import_invalid_mod(self):
        with self.subTest('Test that an invalid import returns an import error.'):
            with patch('tom_alerts.alerts.get_service_classes') as mock_get_service_classes:
                mock_get_service_classes.side_effect = ImportError(f'Could not import {service}. Did you provide the correct path?')
                with self.assertRaises(ImportError):
                    mock_get_service_classes()
