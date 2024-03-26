from django.test import TestCase


class PanSTARRSTestCase(TestCase):
    def setUp(self):
        pass

    def test_can_resolve_target(self):
        self.assertEqual(1, 1)
