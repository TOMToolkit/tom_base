import json

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch
from datetime import date, time
from specutils import Spectrum1D
from astropy import units
import numpy as np

from tom_observations.tests.utils import FakeFacility
from tom_observations.tests.factories import TargetFactory, ObservingRecordFactory
from tom_dataproducts.models import DataProduct, PHOTOMETRY, SPECTROSCOPY
from tom_dataproducts.forms import DataProductUploadForm
from tom_dataproducts.data_processor import DataProcessor
from tom_dataproducts.data_serializers import SpectrumSerializer
from tom_dataproducts.exceptions import InvalidFileFormatException
from guardian.shortcuts import assign_perm


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeFacility'])
@patch('tom_dataproducts.models.DataProduct.get_image_data', return_value=b'image')
class TestObservationDataViews(TestCase):
    def setUp(self):
        self.target = TargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeFacility.name,
            parameters='{}'
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        user = User.objects.create_user(username='test', email='test@example.com')
        assign_perm('tom_targets.view_target', user, self.target)
        self.client.force_login(user)

    def test_dataproduct_list_on_target(self, dp_mock):
        response = self.client.get(reverse('tom_targets:detail', kwargs={'pk': self.target.id}))
        self.assertContains(response, 'afile.fits')

    def test_dataproduct_list(self, dp_mock):
        response = self.client.get(reverse('tom_dataproducts:list'))
        self.assertContains(response, 'afile.fits')

    def test_get_dataproducts(self, dp_mock):
        response = self.client.get(reverse('tom_observations:detail', kwargs={'pk': self.data_product.id}))
        self.assertContains(response, 'testdpid')

    def test_save_dataproduct(self, dp_mock):
        mock_return = [DataProduct(product_id='testdpid', data=SimpleUploadedFile('afile.fits', b'afile'))]
        with patch.object(FakeFacility, 'save_data_products', return_value=mock_return) as mock:
            response = self.client.post(
                reverse('dataproducts:save', kwargs={'pk': self.observation_record.id}),
                data={'facility': 'FakeFacility', 'products': ['testdpid']},
                follow=True
            )
            self.assertTrue(mock.called)
            self.assertContains(response, 'Successfully saved: afile.fits')


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeFacility'])
@patch('tom_dataproducts.views.run_hook')
class TestUploadDataProducts(TestCase):
    def setUp(self):
        self.target = TargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeFacility.name,
            parameters='{}'
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        user = User.objects.create_user(username='test', email='test@example.com')
        assign_perm('tom_targets.view_target', user, self.target)
        self.client.force_login(user)

    def test_upload_data_for_target(self, run_hook_mock):
        response = self.client.post(
            reverse('dataproducts:upload'),
            {
                'facility': 'LCO',
                'files': SimpleUploadedFile('afile.fits', b'afile'),
                'target': self.target.id,
                'tag': SPECTROSCOPY[0],
                'observation_timestamp_0': date(2019, 6, 1),
                'observation_timestamp_1': time(12, 0, 0),
                'referrer': reverse('targets:detail', kwargs={'pk': self.target.id})
            },
            follow=True
        )
        self.assertContains(response, 'Successfully uploaded: {0}/none/afile.fits'.format(self.target.identifier))

    def test_upload_data_for_observation(self, run_hook_mock):
        response = self.client.post(
            reverse('dataproducts:upload'),
            {
                'facility': 'LCO',
                'files': SimpleUploadedFile('bfile.fits', b'afile'),
                'observation_record': self.observation_record.id,
                'tag': SPECTROSCOPY[0],
                'observation_timestamp_0': date(2019, 6, 1),
                'observation_timestamp_1': time(12, 0, 0),
                'referrer': reverse('targets:detail', kwargs={'pk': self.target.id})
            },
            follow=True
        )
        self.assertContains(response, 'Successfully uploaded: {0}/{1}/bfile.fits'.format(
            self.target.identifier, FakeFacility.name)
        )


class TestDataUploadForms(TestCase):
    def setUp(self):
        self.target = TargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeFacility.name,
            parameters='{}'
        )
        self.spectroscopy_form_data = {
            'target': self.target.id,
            'tag': SPECTROSCOPY[0],
            'facility': 'LCO',
            'observation_timestamp_0': date(2019, 6, 1),
            'observation_timestamp_1': time(12, 0, 0),
            'referrer': 'referrer'
        }
        self.photometry_form_data = {
            'target': self.target.id,
            'tag': PHOTOMETRY[0],
            'referrer': 'referrer'
        }
        self.file_data = {
            'files': SimpleUploadedFile('afile.fits', b'afile')
        }

    def test_form_spectroscopy_valid(self):
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertTrue(form.is_valid())

    def test_form_spectroscopy_no_timestamp(self):
        self.spectroscopy_form_data.pop('observation_timestamp_0')
        self.spectroscopy_form_data.pop('observation_timestamp_1')
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertFalse(form.is_valid())

    def test_form_spectroscopy_no_facility(self):
        self.spectroscopy_form_data.pop('facility')
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertFalse(form.is_valid())

    def test_form_photometry_valid(self):
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertTrue(form.is_valid())

    def test_form_photometry_with_timestamp(self):
        self.photometry_form_data['facility'] = 'LCO'
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertFalse(form.is_valid())

    def test_form_photometry_with_facility(self):
        self.photometry_form_data['observation_timestamp_0'] = date(2019, 6, 1)
        self.photometry_form_data['observation_timestamp_1'] = time(12, 0, 0)
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertFalse(form.is_valid())


class TestDataSerializer(TestCase):
    def setUp(self):
        self.serializer = SpectrumSerializer()

    def test_serialize_spectrum(self):
        flux = np.arange(1, 200) * units.Jy
        wavelength = np.arange(1, 200) * units.Angstrom
        spectrum = Spectrum1D(spectral_axis=wavelength, flux=flux)
        serialized = self.serializer.serialize(spectrum)

        self.assertTrue(type(serialized) is str)
        serialized = json.loads(serialized)
        self.assertTrue(serialized['photon_flux'])
        self.assertTrue(serialized['photon_flux_units'])
        self.assertTrue(serialized['wavelength'])
        self.assertTrue(serialized['wavelength_units'])

    def test_serialize_spectrum_invalid(self):
        with self.assertRaises(Exception):
            self.serializer.serialize({'flux': [1, 2], 'wavelength': [1, 2]})

    def test_deserialize_spectrum(self):
        serialized_spectrum = json.dumps({
            'photon_flux': [1, 2],
            'photon_flux_units': 'ph / (Angstrom cm2 s)',
            'wavelength': [1, 2],
            'wavelength_units': 'Angstrom'
        })
        deserialized = self.serializer.deserialize(serialized_spectrum)

        self.assertTrue(type(deserialized) is Spectrum1D)
        self.assertEqual(deserialized.flux.mean().value, 1.5)
        self.assertEqual(deserialized.wavelength.mean().value, 1.5)

    def test_deserialize_spectrum_invalid(self):
        with self.assertRaises(Exception):
            self.serializer.deserialize(json.dumps({'invalid_key': 'value'}))

@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeFacility'])
class TestDataProcessor(TestCase):
    def setUp(self):
        self.target = TargetFactory.create()
        self.data_product = DataProduct.objects.create(
            target=self.target,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        self.data_processor = DataProcessor()

    @patch('tom_dataproducts.data_processor.DataProcessor._process_spectrum_from_fits')
    @patch('tom_dataproducts.data_processor.magic.from_file')
    def test_process_spectroscopy_with_fits_file(self, libmagic_mock, process_data_mock):
        libmagic_mock.return_value = 'image/fits'
        self.data_processor.process_spectroscopy(self.data_product, FakeFacility.name)
        process_data_mock.assert_called_with(self.data_product, FakeFacility.name)

    @patch('tom_dataproducts.data_processor.DataProcessor._process_spectrum_from_plaintext')
    @patch('tom_dataproducts.data_processor.magic.from_file')
    def test_process_spectroscopy_with_plaintext_file(self, libmagic_mock, process_data_mock):
        libmagic_mock.return_value = 'text/plain'
        self.data_processor.process_spectroscopy(self.data_product, FakeFacility.name)
        process_data_mock.assert_called_with(self.data_product, FakeFacility.name)

    @patch('tom_dataproducts.data_processor.magic.from_file')
    def test_process_spectroscopy_with_invalid_file_type(self, libmagic_mock):
        libmagic_mock.return_value = 'image/png'
        with self.assertRaises(InvalidFileFormatException):
            self.data_processor.process_spectroscopy(self.data_product, FakeFacility.name)

    def test_process_spectrum_from_fits(self):
        with open('tom_dataproducts/tests/test_data/test_spectrum.fits', 'rb') as spectrum_file:
            self.data_product.data.save('spectrum.fits', spectrum_file)
            spectrum = self.data_processor._process_spectrum_from_fits(self.data_product, FakeFacility.name)
            self.assertTrue(type(spectrum) is Spectrum1D)
            self.assertAlmostEqual(spectrum.flux.mean().value, 2.295068e-14, places=19)
            self.assertAlmostEqual(spectrum.wavelength.mean().value, 6600.478789, places=5)

    def test_process_spectrum_from_plaintext(self):
        with open('tom_dataproducts/tests/test_data/test_spectrum.csv', 'rb') as spectrum_file:
            self.data_product.data.save('spectrum.csv', spectrum_file)
            spectrum = self.data_processor._process_spectrum_from_plaintext(self.data_product, FakeFacility.name)
            self.assertTrue(type(spectrum) is Spectrum1D)
            self.assertAlmostEqual(spectrum.flux.mean().value, 1.166619e-14, places=19)
            self.assertAlmostEqual(spectrum.wavelength.mean().value, 3250.744489, places=5)

    @patch('tom_dataproducts.data_processor.DataProcessor._process_photometry_from_plaintext')
    @patch('tom_dataproducts.data_processor.magic.from_file')
    def test_process_photometry_with_plaintext_file(self, libmagic_mock, process_data_mock):
        libmagic_mock.return_value = 'text/plain'
        self.data_processor.process_photometry(self.data_product)
        process_data_mock.assert_called_with(self.data_product)

    @patch('tom_dataproducts.data_processor.magic.from_file')
    def test_process_photometry_with_invalid_file_type(self, libmagic_mock):
        libmagic_mock.return_value = 'image/png'
        with self.assertRaises(InvalidFileFormatException):
            self.data_processor.process_photometry(self.data_product)

    def test_process_photometry_from_plaintext(self):
        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.data_product.data.save('lightcurve.csv', lightcurve_file)
            lightcurve = self.data_processor._process_photometry_from_plaintext(self.data_product)
            self.assertTrue(type(lightcurve) is dict)
            self.assertEqual(len(lightcurve), 2)