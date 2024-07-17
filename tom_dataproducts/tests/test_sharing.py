from django.test import TestCase, override_settings

from tom_dataproducts.alertstreams.hermes import create_hermes_alert, BuildHermesMessage, HermesMessageException
from tom_dataproducts.models import ReducedDatum
from tom_observations.tests.utils import FakeRoboticFacility
from tom_observations.tests.factories import SiderealTargetFactory, ObservingRecordFactory
from django.contrib.auth.models import User


DATA_SHARING = {
    'hermes': {
        'DISPLAY_NAME': 'Hermes',
        'BASE_URL': 'http://hermes.test/',
        'HERMES_API_KEY': '123fake',
        'DEFAULT_AUTHORS': 'test author',
        'USER_TOPICS': ['hermes.test', 'tomtoolkit.test'],
    }
}


@override_settings(DATA_SHARING=DATA_SHARING)
class TestHermesSharing(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.user = User.objects.create_user(username='test', email='test@example.com')
        self.rd1 = ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            value={'magnitude': 18.5, 'error': .5, 'filter': 'V', 'telescope': 'tst'}
        )
        self.rd2 = ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            value={'magnitude': 19.5, 'error': .5, 'filter': 'B', 'telescope': 'tst'}
        )
        self.rd3 = ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            value={'magnitude': 17.5, 'error': .5, 'filter': 'R', 'telescope': 'tst'}
        )
        self.rd4 = ReducedDatum.objects.create(
            target=self.target,
            data_type='spectroscopy',
            value={
                'flux': [1, 2, 3],
                'wavelength': [6000, 5999, 5998],
                'error': [0.11, 0.22, 0.33],
                'telescope': 'SpectraTelescope'
            }
        )
        self.rd5 = ReducedDatum.objects.create(
            target=self.target,
            data_type='spectroscopy',
            value={
                '1': {'flux': 20, 'wavelength': 3000},
                '2': {'flux': 21, 'wavelength': 3001},
                '3': {'flux': 22, 'wavelength': 3002},
            }
        )
        self.bad_rd = ReducedDatum.objects.create(
            target=self.target,
            data_type='spectroscopy',
            value={
                'myflux': [1, 2, 3],
                'wavelength_function': 'lambda_xyz'
            }
        )
        self.message_info = BuildHermesMessage(
            title='Test Title',
            submitter=self.user.email,
            authors=self.user.username,
            message='Test Message'
        )

    def _check_alert(self, alert, message_info, datums, targets):
        self.assertEqual(alert['topic'], message_info.topic)
        self.assertEqual(alert['title'], message_info.title)
        self.assertEqual(alert['message_text'], message_info.message)
        self.assertEqual(alert['authors'], message_info.authors)
        self.assertEqual(alert['submitter'], message_info.submitter)
        if targets:
            self.assertEqual(len(alert['data']['targets']), len(targets))
            targets_by_name = {target.name: target for target in targets}
            for target in alert['data']['targets']:
                self.assertIn(target['name'], targets_by_name)
                original_target = targets_by_name[target['name']]
                self.assertEqual(target['ra'], original_target.ra)
                self.assertEqual(target['dec'], original_target.dec)
                self.assertEqual(target['epoch'], original_target.epoch)
                self.assertEqual(target['pm_ra'], original_target.pm_ra)
                self.assertEqual(target['pm_dec'], original_target.pm_dec)
        if datums:
            photometry_datums = len(alert['data'].get('photometry', []))
            spectroscopy_datums = len(alert['data'].get('spectroscopy', []))
            photometry_count = 0
            spectroscopy_count = 0
            self.assertEqual(photometry_datums + spectroscopy_datums, len(datums))
            # These should line up
            for datum in datums:
                if datum.data_type == 'photometry':
                    hermes_datum = alert['data']['photometry'][photometry_count]
                    self.assertEqual(hermes_datum['target_name'], datum.target.name)
                    self.assertEqual(hermes_datum['date_obs'], datum.timestamp.isoformat())
                    self.assertEqual(hermes_datum['telescope'], datum.value.get('telescope'))
                    self.assertEqual(hermes_datum['brightness'], datum.value.get('magnitude'))
                    self.assertEqual(hermes_datum['brightness_error'], datum.value.get('error'))
                    self.assertEqual(hermes_datum['bandpass'], datum.value.get('filter'))
                    photometry_count += 1
                elif datum.data_type == 'spectroscopy':
                    hermes_datum = alert['data']['spectroscopy'][spectroscopy_count]
                    self.assertEqual(hermes_datum['target_name'], datum.target.name)
                    self.assertEqual(hermes_datum['date_obs'], datum.timestamp.isoformat())
                    if 'flux' in datum.value and 'wavelength' in datum.value:
                        self.assertEqual(hermes_datum['flux'], datum.value.get('flux'))
                        self.assertEqual(hermes_datum['wavelength'], datum.value.get('wavelength'))
                        if 'error' in datum.value:
                            self.assertEqual(hermes_datum['flux_error'], datum.value.get('error'))
                    else:
                        for i, entry in enumerate(datum.value.values()):
                            if 'flux' in entry:
                                self.assertEqual(hermes_datum['flux'][i], entry['flux'])
                                self.assertEqual(hermes_datum['wavelength'][i], entry['wavelength'])
                    spectroscopy_count += 1

    def test_convert_to_hermes_format(self):
        datums = [self.rd1, self.rd2, self.rd3]
        targets = [self.target]
        alert = create_hermes_alert(self.message_info, datums, targets)
        # Now check the alerts formatting is correct
        self._check_alert(alert, self.message_info, datums, targets)

    def test_convert_to_hermes_format_extra_target(self):
        target2 = SiderealTargetFactory.create()
        datums = [self.rd1, self.rd2, self.rd3]
        targets = [target2, self.target]
        alert = create_hermes_alert(self.message_info, datums, targets)
        # Now check the alerts formatting is correct
        self._check_alert(alert, self.message_info, datums, targets)

    def test_convert_to_hermes_format_only_targets(self):
        target2 = SiderealTargetFactory.create()
        targets = [target2, self.target]
        alert = create_hermes_alert(self.message_info, [], targets)
        # Now check the alerts formatting is correct
        self._check_alert(alert, self.message_info, [], targets)

    def test_convert_to_hermes_format_only_datums(self):
        datums = [self.rd1, self.rd2, self.rd3]
        alert = create_hermes_alert(self.message_info, datums, [])
        # Now check the alerts formatting is correct
        self._check_alert(alert, self.message_info, datums, [self.target])

    def test_convert_to_hermes_format_spectro_datums(self):
        datums = [self.rd4, self.rd5]
        alert = create_hermes_alert(self.message_info, datums, [])
        # Now check the alerts formatting is correct
        self._check_alert(alert, self.message_info, datums, [self.target])

    def test_convert_to_hermes_format_mixed_datums(self):
        datums = [self.rd1, self.rd2, self.rd3, self.rd4, self.rd5]
        alert = create_hermes_alert(self.message_info, datums, [])
        # Now check the alerts formatting is correct
        self._check_alert(alert, self.message_info, datums, [self.target])

    def test_convert_to_hermes_format_bad_spectro_datum_fails(self):
        datums = [self.rd5, self.bad_rd]
        with self.assertRaises(HermesMessageException):
            create_hermes_alert(self.message_info, datums, [])
