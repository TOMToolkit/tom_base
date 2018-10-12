import math
from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User

import ephem
from astropy import units
from astropy.coordinates import Angle

from .factories import SiderealTargetFactory, NonSiderealTargetFactory
from tom_targets.models import Target


class TestTargetDetail(TestCase):
    def setUp(self):
        user = User.objects.create(username='testuser')
        self.client.force_login(user)
        self.st = SiderealTargetFactory.create()
        self.nst = NonSiderealTargetFactory.create()

    def test_sidereal_target_detail(self):
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.st.id}))
        self.assertContains(response, self.st.id)

    def test_non_sidereal_target_detail(self):
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.nst.id}))
        self.assertContains(response, self.nst.id)

    def test_sidereal_target_create(self):
        response = self.client.get(reverse('targets:create'))
        self.assertContains(response, Target.SIDEREAL)

    def test_non_sidereal_target_create(self):
        response = self.client.get(reverse('targets:create'))
        self.assertContains(response, Target.NON_SIDEREAL)

class TestTargetVisibility(TestCase):
    def setUp(self):
        self.mars = ephem.Mars()
        self.now = datetime.now()
        self.mars.compute(self.now)
        ra = Angle(str(self.mars.ra), unit=units.hourangle)
        dec = Angle(str(self.mars.dec) + 'd', unit=units.deg)
        self.st = Target(ra=ra.deg, dec=dec.deg, type=Target.SIDEREAL)

    def test_get_pyephem_instance_for_sidereal(self):
        target_ephem = self.st.get_pyephem_instance_for_type()
        target_ephem.compute(self.now)
        self.assertIsInstance(target_ephem, type(ephem.FixedBody()))
        self.assertLess(math.fabs(target_ephem.ra-self.mars.ra), 0.5)
        self.assertLess(math.fabs(target_ephem.dec-self.mars.dec), 0.5)

    def test_get_pyephem_instance_for_non_sidereal(self):
        hb = ephem.readdb(
            'C/1995 O1 (Hale-Bopp),e,89.4245,282.4515,130.5641,183.6816,'
            '0.0003959,0.995026,0.1825,07/06.0/1998,2000,g -2.0,4.0'
        )
        nst = Target(
            inclination=89.4245,
            lng_asc_node=282.4515,
            arg_of_perihelion=130.5641,
            semimajor_axis=183.6816,
            mean_daily_motion=0.0003959,
            eccentricity=0.995026,
            mean_anomaly=0.1825,
            ephemeris_epoch=2451000.5,
            type=Target.NON_SIDEREAL
        )
        target_ephem = nst.get_pyephem_instance_for_type()
        location = ephem.city('Los Angeles')
        location.date = ephem.date(self.now)
        hb.compute(location)
        target_ephem.compute(location)
        self.assertLess(math.fabs(target_ephem.ra-hb.ra), 0.5)
        self.assertLess(math.fabs(target_ephem.dec-hb.dec), 0.5)

    def test_get_pyephem_instance_invalid_type(self):
        self.st.type = 'Fake Type'
        self.assertRaises(Exception, self.st.get_pyephem_instance_for_type)

    def test_get_visibility(self):
        # with patch.object(Target, '')
        end = self.now + timedelta(minutes=60)
        visibility_data = self.st.get_visibility(self.now, end, 10, 3)
        self.assertEqual(len(visibility_data), 6)