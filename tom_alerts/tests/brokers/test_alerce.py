from django.tests import override_settings, tag, TestCase

class TestALeRCEBrokerClass(TestCase):
    def setUp(self):
        pass

    # def test_fetch_alerts_payload


@tag('canary')
class TestALeRCEModuleCanary(TestCase):
    def setUp(self):
        pass

    def test_fetch_alerts(self):
        pass

    def test_fetch_alert(self):
        pass

    def test_process_reduced_data(self):
        pass
