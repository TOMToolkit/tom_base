from django.test import tag, TestCase
import unittest

from tom_catalogs.harvesters.jplhorizons import JPLHorizonsHarvester


@unittest.skip("Disable Harvester Tests")
@tag('canary')
class TestJPLHorizonsHarvesterCanary(TestCase):
    def setUp(self):
        self.broker = JPLHorizonsHarvester()

    def test_query_number_only(self):
        self.broker.query('69420')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '69420 (1995 YA1)')
        self.assertEqual(target.names, ['69420 (1995 YA1)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.255042, places=4)
        self.assertAlmostEqual(target.inclination, 13.208657, places=3)
        self.assertAlmostEqual(target.semimajor_axis, 2.58835, places=3)
        self.assertAlmostEqual(target.abs_mag, 15.09, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_designation_only(self):
        self.broker.query('1995 YA1')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '69420 (1995 YA1)')
        self.assertEqual(target.names, ['69420 (1995 YA1)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.255042, places=4)
        self.assertAlmostEqual(target.inclination, 13.208657, places=3)
        self.assertAlmostEqual(target.semimajor_axis, 2.58835, places=3)
        self.assertAlmostEqual(target.abs_mag, 15.09, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_name(self):
        self.broker.query('1627')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '1627 Ivar (1929 SH)')
        self.assertEqual(target.names, ['1627 Ivar (1929 SH)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.3973, places=4)
        self.assertAlmostEqual(target.inclination, 8.4563, places=4)
        self.assertAlmostEqual(target.abs_mag, 12.79, places=2)
        self.assertAlmostEqual(target.slope, 0.60, places=2)

    def test_comet_query_desig(self):
        self.broker.query('P/2012 B1')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, 'PANSTARRS (P/2012 B1)')
        self.assertEqual(target.names, ['PANSTARRS (P/2012 B1)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.410531, places=4)
        self.assertAlmostEqual(target.inclination, 7.605125, places=3)
