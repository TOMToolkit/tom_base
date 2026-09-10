import json
import os
import unittest
from importlib_resources import files

from django.test import TestCase, override_settings, tag
from unittest.mock import MagicMock, patch

import requests

from tom_dataproducts.models import PhotometryReducedDatum
from tom_dataservices.data_services.babamul import BabamulDataService, BabamulForm
from tom_dataservices.dataservices import NotConfiguredError, QueryServiceError
from tom_targets.tests.factories import SiderealTargetFactory

BABAMUL_SETTINGS = {'Babamul': {'api_key': 'test-api-key'}}


def load_fixture(name):
    return json.loads(files('tom_dataservices.tests.test_data').joinpath(name).read_text())


@override_settings(DATA_SERVICES=BABAMUL_SETTINGS)
class TestBabamulDataService(TestCase):
    def setUp(self):
        self.ds = BabamulDataService()
        self.cone_search_response = load_fixture('test_babamul_cone_search.json')
        self.object_response = load_fixture('test_babamul_object.json')
        self.target_result = self.cone_search_response['data'][0]
        self.object_result = self.object_response['data']

    def mock_response(self, payload):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        return mock_response

    def object_copy(self):
        """A deep copy of the object fixture, for tests that mutate it."""
        return json.loads(json.dumps(self.object_result))

    # Query construction

    def test_build_query_parameters_cone_search(self):
        query_parameters = self.ds.build_query_parameters(
            {'ra': 150.0, 'dec': 25.0, 'radius': 300.0, 'limit': 5})
        self.assertEqual(query_parameters, {'ra': 150.0, 'dec': 25.0, 'radius': 300.0, 'limit': 5})

    def test_build_query_parameters_object_id_takes_precedence(self):
        query_parameters = self.ds.build_query_parameters(
            {'object_id': 'ZTF18aahflzc', 'ra': 150.0, 'dec': 25.0, 'radius': 300.0})
        self.assertEqual(query_parameters, {'object_id': 'ZTF18aahflzc'})

    def test_survey_extra_is_authoritative_for_an_existing_target(self):
        """The survey recorded when the target was created wins over the name prefix."""
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')
        target.save(extras={'survey': 'LSST'})

        self.assertEqual(self.ds.build_query_parameters_from_target(target)['survey'], 'LSST')

    def test_survey_falls_back_to_the_object_id_prefix(self):
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')

        self.assertEqual(self.ds.build_query_parameters_from_target(target),
                         {'object_id': 'ZTF18aahflzc', 'survey': 'ZTF'})

    def test_targets_from_other_services_are_not_queried(self):
        """Babamul only serves ZTF and LSST, so a target from elsewhere produces no query."""
        target = SiderealTargetFactory.create(name='M31')

        self.assertEqual(self.ds.build_query_parameters_from_target(target), {})
        self.assertEqual(self.ds.query_photometry({}), {})

    # Transport

    @patch('requests.get')
    def test_query_targets(self, mock_get):
        mock_get.return_value = self.mock_response(self.cone_search_response)

        targets = self.ds.query_targets(
            self.ds.build_query_parameters({'ra': 150.0, 'dec': 25.0, 'radius': 300.0}))

        self.assertEqual(len(targets), 5)
        self.assertEqual(targets[0]['objectId'], 'ZTF20aawqwzt')
        self.assertEqual(mock_get.call_args.args[0], 'https://babamul.caltech.edu/api/babamul/objects')

    @patch('requests.get')
    def test_query_sends_bearer_token_and_a_timeout(self, mock_get):
        mock_get.return_value = self.mock_response(self.cone_search_response)

        self.ds.query_targets({'object_id': 'ZTF18aahflzc'})

        self.assertEqual(mock_get.call_args.kwargs['headers'], {'Authorization': 'Bearer test-api-key'})
        self.assertEqual(mock_get.call_args.kwargs['timeout'], 30)

    @patch('requests.get')
    def test_query_photometry_uses_the_object_endpoint(self, mock_get):
        """The survey and object id select the endpoint, so neither is sent as a query parameter."""
        mock_get.return_value = self.mock_response(self.object_response)

        self.ds.query_photometry({'survey': 'ZTF', 'object_id': 'ZTF18aahflzc'})

        self.assertEqual(mock_get.call_args.args[0],
                         'https://babamul.caltech.edu/api/babamul/surveys/ztf/objects/ZTF18aahflzc')
        self.assertEqual(mock_get.call_args.kwargs['params'], {})

    @patch('requests.get')
    def test_connection_failure_raises_query_service_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError('no route to host')

        with self.assertRaises(QueryServiceError):
            self.ds.query_targets({'object_id': 'ZTF18aahflzc'})

    @patch('requests.get')
    def test_http_error_raises_query_service_error(self, mock_get):
        """A 404, which is what an unknown object id produces, must not escape as an HTTPError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('404 Not Found')
        mock_get.return_value = mock_response

        with self.assertRaises(QueryServiceError):
            self.ds.query_photometry({'survey': 'ZTF', 'object_id': 'ZTFdoesnotexist'})

    @patch('requests.get')
    def test_unparseable_body_raises_query_service_error(self, mock_get):
        """A 200 carrying an HTML error page must not escape as a JSONDecodeError."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError('Expecting value')
        mock_get.return_value = mock_response

        with self.assertRaises(QueryServiceError):
            self.ds.query_targets({'object_id': 'ZTF18aahflzc'})

    @patch('requests.get')
    def test_response_without_a_data_key_raises_query_service_error(self, mock_get):
        """A malformed success response must not be reported to the user as an empty result."""
        mock_get.return_value = self.mock_response({'message': 'something unexpected'})

        with self.assertRaises(QueryServiceError):
            self.ds.query_targets({'object_id': 'ZTF18aahflzc'})

    @override_settings(DATA_SERVICES={'Babamul': {}})
    @patch('requests.get')
    def test_missing_api_key_raises_not_configured(self, mock_get):
        """A configured service with no api_key must report that, not send a literal 'Bearer None'."""
        with self.assertRaises(NotConfiguredError):
            self.ds.query_targets({'object_id': 'ZTF18aahflzc'})
        mock_get.assert_not_called()

    @override_settings(DATA_SERVICES={'SomeOtherService': {}})
    @patch('requests.get')
    def test_unconfigured_service_raises_not_configured(self, mock_get):
        """RunQueryView renders NotConfiguredError with a link to the configuration documentation."""
        with self.assertRaises(NotConfiguredError):
            self.ds.query_targets({'object_id': 'ZTF18aahflzc'})
        mock_get.assert_not_called()

    # Targets

    def test_to_target(self):
        target = self.ds.to_target(self.target_result)

        self.assertEqual(target.name, 'ZTF20aawqwzt')
        self.assertEqual(target.type, 'SIDEREAL')
        self.assertAlmostEqual(target.ra, 149.9989633, places=7)
        self.assertAlmostEqual(target.dec, 25.0053292, places=7)

    def test_query_specific_fields_are_not_persisted_as_extras(self):
        """distance_arcsec belongs to the search, not the object, and id is the view's cache index."""
        target_result = dict(self.target_result, id=7)

        extras = self.ds.create_target_extras_from_query(target_result)

        self.assertEqual(extras, {'survey': 'ZTF'})

    # Photometry

    def test_create_reduced_datums_from_query(self):
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')

        reduced_datums = self.ds.create_reduced_datums_from_query(target, self.object_result)

        # 2 distinct detections plus 48 non-detections with a limiting magnitude.
        self.assertEqual(len(reduced_datums), 50)
        self.assertEqual(len([d for d in reduced_datums if d.brightness is not None]), 2)
        self.assertEqual(len([d for d in reduced_datums if d.limit is not None]), 48)
        self.assertEqual(PhotometryReducedDatum.objects.filter(target=target).count(), 50)

    def test_the_latest_detection_is_not_ingested_twice(self):
        """`candidate` also appears in `prv_candidates`, so detections are deduplicated by candid."""
        candidate = self.object_result['candidate']
        self.assertIn(candidate['candid'], [c['candid'] for c in self.object_result['prv_candidates']])

        detections = BabamulDataService.detections(self.object_result)

        self.assertEqual([d['candid'] for d in detections].count(candidate['candid']), 1)

    def test_reingesting_the_same_object_creates_no_duplicates(self):
        """A second sync must be idempotent, including when the reported uncertainty has changed."""
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')
        self.ds.create_reduced_datums_from_query(target, self.object_result)

        resynced = self.object_copy()
        resynced['candidate']['sigmapsf'] = 0.2
        self.ds.create_reduced_datums_from_query(target, resynced)

        self.assertEqual(PhotometryReducedDatum.objects.filter(target=target).count(), 50)

    def test_detections_carry_brightness_and_band(self):
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')

        first = self.ds.create_reduced_datums_from_query(target, self.object_result)[0]

        self.assertEqual(first.target, target)
        self.assertEqual(first.unit, 'mag')
        self.assertEqual(first.bandpass, 'r')
        self.assertEqual(first.source_name, 'Babamul')
        self.assertAlmostEqual(first.brightness, 18.46976089477539, places=6)
        self.assertAlmostEqual(first.brightness_error, 0.10326997935771942, places=6)
        # Babamul reports Julian Date, not Modified Julian Date: JD 2459859.0226157 is 2022-10-06 12:32 UTC.
        self.assertEqual(first.timestamp.strftime('%Y-%m-%d %H:%M'), '2022-10-06 12:32')

    def test_bandpass_follows_the_reported_band(self):
        """Every measurement in the fixture is r, so vary it to prove the band is actually read."""
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')
        object_result = self.object_copy()
        object_result['candidate']['band'] = 'g'
        object_result['prv_candidates'] = []
        object_result['prv_nondetections'] = []

        reduced_datum = self.ds.create_reduced_datums_from_query(target, object_result)[0]

        self.assertEqual(reduced_datum.bandpass, 'g')

    def test_non_detections_are_stored_as_limits(self):
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')

        reduced_datums = self.ds.create_reduced_datums_from_query(target, self.object_result)
        limit = [datum for datum in reduced_datums if datum.limit is not None][0]

        self.assertIsNone(limit.brightness)
        self.assertAlmostEqual(limit.limit, 17.555099487304688, places=6)
        self.assertEqual(limit.bandpass, 'r')

    def test_measurements_without_a_magnitude_are_skipped(self):
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')
        object_result = self.object_copy()
        for detection in [object_result['candidate']] + object_result['prv_candidates']:
            detection['magpsf'] = None
        object_result['prv_nondetections'] = []

        self.assertEqual(self.ds.create_reduced_datums_from_query(target, object_result), [])

    def test_measurements_without_a_band_are_skipped(self):
        """bandpass is not nullable, so a malformed measurement must be skipped, not saved."""
        target = SiderealTargetFactory.create(name='ZTF18aahflzc')
        object_result = self.object_copy()
        object_result['candidate'].pop('band')
        object_result['prv_candidates'] = []
        object_result['prv_nondetections'][0].pop('band')
        object_result['prv_nondetections'] = object_result['prv_nondetections'][:1]

        self.assertEqual(self.ds.create_reduced_datums_from_query(target, object_result), [])

    def test_create_reduced_datums_from_empty_query(self):
        target = SiderealTargetFactory.create(name='ZTF20aawqwzt')

        self.assertEqual(self.ds.create_reduced_datums_from_query(target, {}), [])
        self.assertEqual(self.ds.create_reduced_datums_from_query(target, None), [])


class TestBabamulForm(TestCase):
    """``data_service`` is a required hidden field on ``BaseQueryForm``, so every case must supply it."""

    def form(self, **data):
        return BabamulForm({'data_service': 'Babamul', **data})

    def test_form_accepts_a_cone_search(self):
        self.assertTrue(self.form(ra=150.0, dec=25.0, radius=300.0).is_valid())

    def test_form_accepts_an_object_id(self):
        self.assertTrue(self.form(object_id='ZTF18aahflzc').is_valid())

    def test_form_rejects_a_partial_cone_search(self):
        form = self.form(ra=150.0)

        self.assertFalse(form.is_valid())
        self.assertIn('Please provide either an Object ID', str(form.errors))

    def test_form_rejects_a_zero_radius(self):
        """A zero radius is a cone that can never match anything."""
        form = self.form(ra=150.0, dec=25.0, radius=0)

        self.assertFalse(form.is_valid())
        self.assertIn('radius', form.errors)

    def test_form_rejects_an_empty_query(self):
        self.assertFalse(self.form().is_valid())


@tag('canary')
@unittest.skipUnless(os.environ.get('BABAMUL_API_KEY'),
                     'Set BABAMUL_API_KEY to run the Babamul canary test.')
@override_settings(DATA_SERVICES={'Babamul': {'api_key': os.environ.get('BABAMUL_API_KEY')}})
class TestBabamulCanary(TestCase):
    """
    Hits the live Babamul API. Excluded from the default test run, and skipped unless BABAMUL_API_KEY is
    set, so that the scheduled canary job does not fail on an installation without Babamul credentials.
    """

    def test_cone_search_returns_objects(self):
        results = BabamulDataService().query_targets({'ra': 150.0, 'dec': 25.0, 'radius': 300.0, 'limit': 3})

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIn('objectId', result)
            self.assertIn('ra', result)
            self.assertIn('dec', result)
