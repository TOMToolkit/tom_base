from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User

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
