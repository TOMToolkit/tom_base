from django.shortcuts import reverse
from django.test import override_settings, tag, TestCase


@tag('canary')
class TestMPCHarvesterCanary(TestCase):
    @override_settings(TOM_HARVESTER_CLASSES=['tom_catalogs.harvesters.mpc.MPCHarvester'])
    def test_import_incorrect_version(self):
        """Test that MPC import fails, as the available version of astroquery contains a bug."""
        with self.assertRaisesRegex(ImportError, 'Please consult the TOM Toolkit harvester API docs and '
                                                 'ensure that your version of astroquery is at least 0.4.2.dev0.'):
            self.client.get(reverse('tom_catalogs:query'))
