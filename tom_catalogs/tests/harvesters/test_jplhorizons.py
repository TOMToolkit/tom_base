from django.test import tag, TestCase

from tom_catalogs.harvesters.jplhorizons import JPLHorizonsHarvester


@tag('canary')
class TestJPLHorizonsHarvesterCanary(TestCase):
    def setUp(self):
        self.broker = JPLHorizonsHarvester()

    def test_query_number_only(self):
        self.broker.query('700000')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '700000 (1994 UX10)')
        self.assertEqual(target.names, ['700000 (1994 UX10)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.093, places=3)
        self.assertAlmostEqual(target.inclination, 4.1684084, places=3)
        self.assertAlmostEqual(target.semimajor_axis, 2.657503, places=3)
        self.assertAlmostEqual(target.abs_mag, 17.76, places=2)
        self.assertAlmostEqual(target.slope, 0.15, places=2)

    def test_query_designation_only(self):
        self.broker.query('2025 MB18')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, '(2025 MB18)')
        self.assertEqual(target.names, ['(2025 MB18)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_MINOR_PLANET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.1386, places=4)
        self.assertAlmostEqual(target.inclination, 19.2780, places=4)
        self.assertAlmostEqual(target.abs_mag, 24.33, places=2)
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
        self.broker.query('C/2025 A6')
        target = self.broker.to_target()
        target.save(names=getattr(target, 'extra_names', []))
        # Only test things that are not likely to change (much) with time
        self.assertEqual(target.name, 'Lemmon (C/2025 A6)')
        self.assertEqual(target.names, ['Lemmon (C/2025 A6)'])
        self.assertEqual(target.type, 'NON_SIDEREAL')
        self.assertEqual(target.scheme, 'MPC_COMET')
        self.assertEqual(target.ra, None)
        self.assertEqual(target.dec, None)
        self.assertAlmostEqual(target.eccentricity, 0.9956, places=4)
        self.assertAlmostEqual(target.inclination, 143.663531, places=3)
