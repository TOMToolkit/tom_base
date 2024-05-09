import datetime
from http import HTTPStatus
import os
import tempfile
import responses

from astropy import units
from astropy.io import fits
from astropy.table import Table
from datetime import date, time
from django.test import TestCase, override_settings
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from guardian.shortcuts import assign_perm
import numpy as np
from specutils import Spectrum1D
from unittest.mock import patch

from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.forms import DataProductUploadForm
from tom_dataproducts.models import DataProduct, is_fits_image_file, ReducedDatum, data_product_path
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_dataproducts.processors.photometry_processor import PhotometryProcessor
from tom_dataproducts.processors.spectroscopy_processor import SpectroscopyProcessor
from tom_dataproducts.utils import create_image_dataproduct
from tom_observations.tests.utils import FakeRoboticFacility
from tom_observations.tests.factories import SiderealTargetFactory, ObservingRecordFactory


def mock_fits2image(file1, file2, width, height):
    return True


def mock_find_fits_img_size(filename):
    return (0, 0)


def mock_is_fits_image_file(filename):
    return True


def dp_path(instance, filename):
    return f'new_path/{filename}'


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
@patch('tom_dataproducts.models.DataProduct.get_preview', return_value='/no-image.jpg')
class Views(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
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

    def test_get_dataproducts(self, dp_mock):
        response = self.client.get(reverse('tom_observations:detail', kwargs={'pk': self.observation_record.id}))
        self.assertContains(response, 'testdpid')

    def test_save_dataproduct(self, dp_mock):
        mock_return = [DataProduct(product_id='testdpid', data=SimpleUploadedFile('afile.fits', b'afile'))]
        with patch.object(FakeRoboticFacility, 'save_data_products', return_value=mock_return) as mock:
            response = self.client.post(
                reverse('dataproducts:save', kwargs={'pk': self.observation_record.id}),
                data={'facility': 'FakeRoboticFacility', 'products': ['testdpid']},
                follow=True
            )
            self.assertTrue(mock.called)
            self.assertContains(response, 'Successfully saved: afile.fits')

    # Non-FITS file
    def test_is_fits_image_file_invalid_fits(self, dp_mock):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                nonfits_file = os.path.join(tmpdir, 'nonfits.fits')
                with open(nonfits_file, 'w') as f:
                    f.write('hello')
                self.data_product.data = nonfits_file
                self.assertFalse(is_fits_image_file(self.data_product.data))

    # Binary table: not image data
    def test_is_fits_image_file_binary_table(self, dp_mock):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                table_file = os.path.join(tmpdir, 'table.fits')
                t = Table([[1, 2], [4, 5], [7, 8]], names=('a', 'b', 'c'))
                t.write(table_file, format='fits')
                self.data_product.data = table_file
                self.assertFalse(is_fits_image_file(self.data_product.data))

    # Image file
    def test_is_fits_image_file_img(self, dp_mock):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                img_file = os.path.join(tmpdir, 'img.blah')  # file name should be irrelevant
                img = fits.PrimaryHDU(np.arange(100))
                img.header['EXTNAME'] = 'SCI'
                hdul = fits.HDUList([img])
                hdul.writeto(img_file)
                self.data_product.data = img_file
                self.assertTrue(is_fits_image_file(self.data_product.data.file))

    # Table + image data
    def test_is_fits_image_file_table_img(self, dp_mock):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                img_file = os.path.join(tmpdir, 'img.blah')  # file name should be irrelevant
                img = fits.PrimaryHDU(np.arange(100))
                img.header['EXTNAME'] = 'SCI'
                hdul = fits.HDUList([img])
                hdul.writeto(img_file)

                tabimg_file = os.path.join(tmpdir, 'both.fits')
                table = fits.BinTableHDU.from_columns([
                    fits.Column(name='col1', format='I', array=np.array([1, 2, 3])),
                    fits.Column(name='col2', format='I', array=np.array([4, 5, 6]))
                ])
                hdul = fits.HDUList([img, table])
                hdul.writeto(tabimg_file)
                self.data_product.data = tabimg_file
                self.assertTrue(is_fits_image_file(self.data_product.data.file))

    @patch('tom_dataproducts.models.fits_to_jpg', mock_fits2image)
    @patch('tom_dataproducts.models.find_fits_img_size', mock_find_fits_img_size)
    @patch('tom_dataproducts.models.is_fits_image_file', mock_is_fits_image_file)
    def test_create_jpeg(self, dp_mock):
        products = DataProduct.objects.filter(data_product_type='image_file')
        self.assertEqual(products.count(), 0)
        resp = create_image_dataproduct(self.data_product)
        self.assertTrue(resp)
        products = DataProduct.objects.filter(data_product_type='image_file')
        self.assertEqual(products.count(), 1)


class TestModels(TestCase):
    def setUp(self):
        self.overide_path = 'tom_dataproducts.tests.tests.dp_path'
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )

    def test_no_path_overide(self):
        """Test that the default path is used if no overide is set"""
        filename = 'afile.fits'
        path = data_product_path(self.data_product, filename)
        self.assertIn(f'FakeRoboticFacility/{filename}', path)

    @override_settings(DATA_PRODUCT_PATH='tom_dataproducts.tests.tests.dp_path')
    def test_path_overide(self):
        """Test that the overide path is used if set"""
        path = data_product_path(self.data_product, 'afile.fits')
        self.assertIn('new_path/afile.fits', path)


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=False)
@patch('tom_dataproducts.models.DataProduct.get_preview', return_value='/no-image.jpg')
class TestViewsWithPermissions(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        self.user = User.objects.create_user(username='aaronrodgers', email='aaron.rodgers@packers.com')
        self.user2 = User.objects.create_user(username='timboyle', email='tim.boyle@packers.com')
        assign_perm('tom_targets.view_target', self.user, self.target)
        assign_perm('tom_targets.view_target', self.user2, self.target)
        assign_perm('tom_targets.view_dataproduct', self.user, self.data_product)
        self.client.force_login(self.user)

    def test_dataproduct_list_on_target(self, dp_mock):
        response = self.client.get(reverse('tom_targets:detail', kwargs={'pk': self.target.id}))
        self.assertContains(response, 'afile.fits')
        self.client.force_login(self.user2)

    def test_dataproduct_list_on_target_unauthorized(self, dp_mock):
        self.client.force_login(self.user2)
        response = self.client.get(reverse('tom_targets:detail', kwargs={'pk': self.target.id}))
        self.assertNotContains(response, 'afile.fits')

    def test_dataproduct_list(self, dp_mock):
        response = self.client.get(reverse('tom_dataproducts:list'))
        self.assertContains(response, 'afile.fits')

    def test_dataproduct_list_unauthorized(self, dp_mock):
        self.client.force_login(self.user2)
        response = self.client.get(reverse('tom_dataproducts:list'))
        self.assertNotContains(response, 'afile.fits')

    @override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                       TARGET_PERMISSIONS_ONLY=False)
    def test_upload_data_extended_permissions(self, dp_mock):
        group = Group.objects.create(name='permitted')
        group.user_set.add(self.user)
        response = self.client.post(
            reverse('dataproducts:upload'),
            {
                'facility': 'LCO',
                'files': SimpleUploadedFile('afile.fits', b'afile'),
                'target': self.target.id,
                'groups': Group.objects.filter(name='permitted'),
                'data_product_type': settings.DATA_PRODUCT_TYPES['spectroscopy'][0],
                'observation_timestamp_0': date(2019, 6, 1),
                'observation_timestamp_1': time(12, 0, 0),
                'referrer': reverse('targets:detail', kwargs={'pk': self.target.id})
            },
            follow=True
        )
        self.assertContains(response, 'afile.fits')
        self.client.force_login(self.user2)
        response = self.client.get(reverse('targets:detail', kwargs={'pk': self.target.id}))
        self.assertNotContains(response, 'afile.fits')


class TestDataProductListView(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        user = User.objects.create_user(username='test', email='test@example.com')
        assign_perm('tom_targets.view_target', user, self.target)
        self.client.force_login(user)

    @patch('tom_dataproducts.models.DataProduct.get_preview', return_value='/no-image.jpg')
    def test_dataproduct_list(self, dp_mock):
        """Test that the data product list view renders correctly."""
        response = self.client.get(reverse('tom_dataproducts:list'))
        self.assertContains(response, 'afile.fits')

    @patch('tom_dataproducts.models.is_fits_image_file')
    def test_dataproduct_list_no_thumbnail(self, mock_is_fits_image_file):
        """Test that a data product with a failed thumbnail creation does not raise an exception."""
        mock_is_fits_image_file.return_value = True
        response = self.client.get(reverse('tom_dataproducts:list'))
        self.assertEqual(response.status_code, HTTPStatus.OK)


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True)
@patch('tom_dataproducts.views.run_data_processor')
class TestUploadDataProducts(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        self.user = User.objects.create_user(username='test', email='test@example.com')
        assign_perm('tom_targets.view_target', self.user, self.target)
        self.client.force_login(self.user)

    def test_upload_data_for_target(self, run_data_processor_mock):
        response = self.client.post(
            reverse('dataproducts:upload'),
            {
                'facility': 'LCO',
                'files': SimpleUploadedFile('afile.fits', b'afile'),
                'target': self.target.id,
                'data_product_type': settings.DATA_PRODUCT_TYPES['spectroscopy'][0],
                'observation_timestamp_0': date(2019, 6, 1),
                'observation_timestamp_1': time(12, 0, 0),
                'referrer': reverse('targets:detail', kwargs={'pk': self.target.id})
            },
            follow=True
        )
        self.assertContains(response, 'Successfully uploaded: {0}/none/afile.fits'.format(self.target.name))

    def test_upload_data_for_observation(self, run_data_processor_mock):
        response = self.client.post(
            reverse('dataproducts:upload'),
            {
                'facility': 'LCO',
                'files': SimpleUploadedFile('bfile.fits', b'afile'),
                'observation_record': self.observation_record.id,
                'data_product_type': settings.DATA_PRODUCT_TYPES['spectroscopy'][0],
                'observation_timestamp_0': date(2019, 6, 1),
                'observation_timestamp_1': time(12, 0, 0),
                'referrer': reverse('targets:detail', kwargs={'pk': self.target.id})
            },
            follow=True
        )
        self.assertContains(response, 'Successfully uploaded: {0}/{1}/bfile.fits'.format(
            self.target.name, FakeRoboticFacility.name)
        )


class TestDeleteDataProducts(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        self.user = User.objects.create_user(username='aaronrodgers', email='aaron.rodgers@packers.com')
        self.user2 = User.objects.create_user(username='timboyle', email='tim.boyle@packers.com')
        assign_perm('tom_targets.view_target', self.user, self.target)
        assign_perm('tom_targets.view_target', self.user2, self.target)
        assign_perm('tom_targets.view_dataproduct', self.user, self.data_product)
        assign_perm('tom_targets.view_dataproduct', self.user2, self.data_product)
        assign_perm('tom_targets.delete_dataproduct', self.user, self.data_product)
        self.client.force_login(self.user)

    def test_delete_data_product_target_permissions_only(self):
        response = self.client.post(reverse('dataproducts:delete', kwargs={'pk': self.data_product.id}), follow=True)
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(DataProduct.objects.filter(product_id='testproductid').exists())

    @override_settings(TARGET_PERMISSIONS_ONLY=False)
    def test_delete_data_product_unauthorized(self):
        self.client.force_login(self.user2)
        response = self.client.post(reverse('dataproducts:delete', kwargs={'pk': self.data_product.id}), follow=True)
        self.assertRedirects(response, reverse('login') + f'?next=/dataproducts/data/{self.data_product.id}/delete/')
        self.assertTrue(DataProduct.objects.filter(product_id='testproductid').exists())

    @override_settings(TARGET_PERMISSIONS_ONLY=False)
    def test_delete_data_product_authorized(self):
        response = self.client.post(reverse('dataproducts:delete', kwargs={'pk': self.data_product.id}), follow=True)
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(DataProduct.objects.filter(product_id='testproductid').exists())


class TestDataUploadForms(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.spectroscopy_form_data = {
            'target': self.target.id,
            'data_product_type': settings.DATA_PRODUCT_TYPES['spectroscopy'][0],
            'facility': 'LCO',
            'observation_timestamp_0': date(2019, 6, 1),
            'observation_timestamp_1': time(12, 0, 0),
            'referrer': 'referrer'
        }
        self.photometry_form_data = {
            'target': self.target.id,
            'data_product_type': settings.DATA_PRODUCT_TYPES['photometry'][0],
            'referrer': 'referrer'
        }
        self.file_data = {
            'files': SimpleUploadedFile('afile.fits', b'afile')
        }

    def test_form_spectroscopy_valid(self):
        form = DataProductUploadForm(self.spectroscopy_form_data, self.file_data)
        self.assertTrue(form.is_valid())

    def test_form_photometry_valid(self):
        form = DataProductUploadForm(self.photometry_form_data, self.file_data)
        self.assertTrue(form.is_valid())


class TestDataSerializer(TestCase):
    def setUp(self):
        self.serializer = SpectrumSerializer()

    def test_serialize_spectrum(self):
        flux = np.arange(1, 200) * units.Jy
        wavelength = np.arange(1, 200) * units.Angstrom
        spectrum = Spectrum1D(spectral_axis=wavelength, flux=flux)
        serialized = self.serializer.serialize(spectrum)

        self.assertTrue(isinstance(serialized, dict))
        self.assertTrue(serialized['flux'])
        self.assertTrue(serialized['flux_units'])
        self.assertTrue(serialized['wavelength'])
        self.assertTrue(serialized['wavelength_units'])

    def test_serialize_spectrum_invalid(self):
        with self.assertRaises(Exception):
            self.serializer.serialize({'flux': [1, 2], 'wavelength': [1, 2]})

    def test_deserialize_spectrum(self):
        serialized_spectrum = {
            'flux': [1, 2],
            'flux_units': 'ph / (Angstrom cm2 s)',
            'wavelength': [1, 2],
            'wavelength_units': 'Angstrom'
        }
        deserialized = self.serializer.deserialize(serialized_spectrum)

        self.assertTrue(isinstance(deserialized, Spectrum1D))
        self.assertEqual(deserialized.flux.mean().value, 1.5)
        self.assertEqual(deserialized.wavelength.mean().value, 1.5)

    def test_deserialize_spectrum_invalid(self):
        with self.assertRaises(Exception):
            self.serializer.deserialize({'invalid_key': 'value'})


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'])
class TestDataProcessor(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.data_product = DataProduct.objects.create(
            target=self.target
        )
        self.spectrum_data_processor = SpectroscopyProcessor()
        self.photometry_data_processor = PhotometryProcessor()
        self.test_file = SimpleUploadedFile('afile.fits', b'somedata')

    @patch('tom_dataproducts.processors.spectroscopy_processor.SpectroscopyProcessor._process_spectrum_from_fits',
           return_value=('', '', ''))
    @patch('tom_dataproducts.processors.spectroscopy_processor.SpectrumSerializer.serialize', return_value={})
    def test_process_spectroscopy_with_fits_file(self, serializer_mock, process_data_mock):
        self.data_product.data.save('spectrum.fits', self.test_file)
        self.spectrum_data_processor.process_data(self.data_product)
        process_data_mock.assert_called_with(self.data_product)

    @patch('tom_dataproducts.processors.spectroscopy_processor.SpectroscopyProcessor._process_spectrum_from_plaintext',
           return_value=('', '', ''))
    @patch('tom_dataproducts.processors.spectroscopy_processor.SpectrumSerializer.serialize', return_value={})
    def test_process_spectroscopy_with_plaintext_file(self, serializer_mock, process_data_mock):
        self.data_product.data.save('spectrum.csv', self.test_file)
        self.spectrum_data_processor.process_data(self.data_product)
        process_data_mock.assert_called_with(self.data_product)

    def test_process_spectroscopy_with_invalid_file_type(self):
        self.data_product.data.save('spectrum.png', self.test_file)
        with self.assertRaises(InvalidFileFormatException):
            self.spectrum_data_processor.process_data(self.data_product)

    def test_process_spectrum_from_fits(self):
        with open('tom_dataproducts/tests/test_data/test_spectrum.fits', 'rb') as spectrum_file:
            self.data_product.data.save('spectrum.fits', spectrum_file)
            spectrum, _, _ = self.spectrum_data_processor._process_spectrum_from_fits(self.data_product)
            self.assertTrue(isinstance(spectrum, Spectrum1D))
            self.assertAlmostEqual(spectrum.flux.mean().value, 2.295068e-14, places=19)
            self.assertAlmostEqual(spectrum.wavelength.mean().value, 6600.478789, places=5)

    def test_process_spectrum_from_plaintext(self):
        with open('tom_dataproducts/tests/test_data/test_spectrum.csv', 'rb') as spectrum_file:
            self.data_product.data.save('spectrum.csv', spectrum_file)
            spectrum, _, _ = self.spectrum_data_processor._process_spectrum_from_plaintext(self.data_product)
            self.assertTrue(isinstance(spectrum, Spectrum1D))
            self.assertAlmostEqual(spectrum.flux.mean().value, 1.166619e-14, places=19)
            self.assertAlmostEqual(spectrum.wavelength.mean().value, 3250.744489, places=5)

    @patch('tom_dataproducts.processors.photometry_processor.PhotometryProcessor._process_photometry_from_plaintext')
    def test_process_photometry_with_plaintext_file(self, process_data_mock):
        self.data_product.data.save('lightcurve.csv', self.test_file)
        self.photometry_data_processor.process_data(self.data_product)
        process_data_mock.assert_called_with(self.data_product)

    def test_process_photometry_with_invalid_file_type(self):
        self.data_product.data.save('lightcurve.blah', self.test_file)
        with self.assertRaises(InvalidFileFormatException):
            self.photometry_data_processor.process_data(self.data_product)

    def test_process_photometry_from_plaintext(self):
        with open('tom_dataproducts/tests/test_data/test_lightcurve.csv', 'rb') as lightcurve_file:
            self.data_product.data.save('lightcurve.csv', lightcurve_file)
            lightcurve = self.photometry_data_processor._process_photometry_from_plaintext(self.data_product)
            self.assertTrue(isinstance(lightcurve, list))
            self.assertEqual(len(lightcurve), 3)


class TestDataProductModel(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.data_product = DataProduct.objects.create(
            product_id='test_product_id',
            target=self.target,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )

    @patch('tom_dataproducts.models.is_fits_image_file')
    def test_create_thumbnail(self, mock_is_fits_image_file):
        """Test that a failed thumbnail creation logs the correct message and does not break."""
        mock_is_fits_image_file.return_value = True
        with self.assertLogs('tom_dataproducts.models', level='WARN') as logs:
            self.data_product.create_thumbnail()
            expected = ('WARNING:tom_dataproducts.models:Unable to create thumbnail '
                        f'for {self.data_product}: No SIMPLE card found, this file does not appear'
                        ' to be a valid FITS file. If this is really a FITS file, try with '
                        'ignore_missing_simple=True')

            self.assertIn(expected, logs.output)


class TestReducedDatumModel(TestCase):
    def setUp(self):
        # set up a ReducedDatum instance to test against
        self.target = SiderealTargetFactory.create()
        self.data_type = 'photometry'
        self.source_name = 'test_source'
        self.timestamp = datetime.datetime.now()
        self.existing_reduced_datum_value = {
            'magnitude': 18.5,
            'error': .5,
            'filter': 'r',
            'telescope': 'ELP.domeA.1m0a',
            'instrument': 'fa07'}
        self.existing_reduced_datum = ReducedDatum.objects.create(
            target=self.target,
            data_type=self.data_type,
            source_name=self.source_name,
            timestamp=self.timestamp,
            value=self.existing_reduced_datum_value)

    def test_create_reduced_datum(self):
        """Test that we can add a second unique ReducedDatum"""
        second_reduced_datum_value = {
            'magnitude': 10.5,
            'error': 1.5,
            'filter': 'g',
            'telescope': 'ELP.domeA.1m0a',
            'instrument': 'fa07'}

        ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            source_name='test_source',
            timestamp=self.timestamp,
            value=second_reduced_datum_value)

        self.assertEqual(2, ReducedDatum.objects.count())

    def test_create_reduced_datum_duplicate(self):
        """Test that we cannot add a second ReducedDatum with the same target, data_type,
        timestamp, and value dict"""
        # in this case ALL fields are the same as the self.existing_reduced_datum
        with self.assertRaises(ValidationError):
            ReducedDatum.objects.create(
                target=self.target,
                data_type=self.data_type,
                source_name=self.source_name,
                timestamp=self.timestamp,
                value=self.existing_reduced_datum_value)

        # in this case only the target, data_type and value fields
        # are the same as the self.existing_reduced_datum
        # so an exception should NOT be raised
        try:
            ReducedDatum.objects.create(
                target=self.target,
                data_type=self.data_type,
                source_name='new_source_name',
                timestamp=(self.timestamp - datetime.timedelta(days=1)),  # different timestamp
                value=self.existing_reduced_datum_value)
        except ValidationError:
            self.fail("ValidationError raised when it should not have been (timestamps differ)")

        # by NOT raising ValidationError, this shows that
        # ReducedDatum.objects.bulk_create() bypasses the ReducedDatum.save()
        # method which validated uniqueness!!
        # (this is a duplicate ReducedDatum that we are trying to add here
        unsaved_reduced_datum = ReducedDatum(
            target=self.target,
            data_type=self.data_type,
            source_name=self.source_name,
            timestamp=self.timestamp,
            value=self.existing_reduced_datum_value)
        # does bulk_create bypass the ReducedDatum.save() method which validated uniqueness?
        # (this is a duplicate ReducedDatum that we are trying to add here
        ReducedDatum.objects.bulk_create([unsaved_reduced_datum])


@override_settings(TOM_FACILITY_CLASSES=['tom_observations.tests.utils.FakeRoboticFacility'],
                   TARGET_PERMISSIONS_ONLY=True,
                   DATA_SHARING={'local_host': {'BASE_URL': 'https://fake.url/example/',
                                                'USERNAME': 'fake_user',
                                                'PASSWORD': 'password'}})
class TestShareDataProducts(TestCase):
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
            facility=FakeRoboticFacility.name,
            parameters={}
        )
        self.data_product = DataProduct.objects.create(
            product_id='testproductid',
            target=self.target,
            observation_record=self.observation_record,
            data=SimpleUploadedFile('afile.fits', b'somedata')
        )
        self.user = User.objects.create_user(username='test', email='test@example.com')
        assign_perm('tom_targets.view_target', self.user, self.target)
        self.client.force_login(self.user)

        self.rd1 = ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            value={'magnitude': 18.5, 'error': .5, 'filter': 'V'}
        )
        self.rd2 = ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            value={'magnitude': 19.5, 'error': .5, 'filter': 'B'}
        )
        self.rd3 = ReducedDatum.objects.create(
            target=self.target,
            data_type='photometry',
            value={'magnitude': 17.5, 'error': .5, 'filter': 'R'}
        )

    @responses.activate
    def test_share_dataproduct_no_valid_responses(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"error": "not found"},
            status=500
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )

        response = self.client.post(
            reverse('dataproducts:share', kwargs={'dp_pk': self.data_product.id}),
            {
                'share_authors': ['test_author'],
                'target': self.target.id,
                'submitter': ['test_submitter'],
                'share_destination': [share_destination],
                'share_title': ['Updated data for thingy.'],
                'share_message': ['test_message']
            },
            follow=True
        )
        self.assertContains(response, 'ERROR: No matching target found.')

    @responses.activate
    def test_share_reduceddatums_target_no_valid_responses(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"error": "not found"},
            status=500
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )

        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            {
                'share_authors': ['test_author'],
                'target': self.target.id,
                'submitter': ['test_submitter'],
                'share_destination': [share_destination],
                'share_title': ['Updated data for thingy.'],
                'share_message': ['test_message']
            },
            follow=True
        )
        self.assertContains(response, 'ERROR: No matching target found.')

    @responses.activate
    def test_share_reduced_datums_no_valid_responses(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"error": "not found"},
            status=500
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )

        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            {
                'share_authors': ['test_author'],
                'target': self.target.id,
                'submitter': ['test_submitter'],
                'share_destination': [share_destination],
                'share_title': ['Updated data for thingy.'],
                'share_message': ['test_message'],
                'share-box': [1, 2]
            },
            follow=True
        )
        self.assertContains(response, 'ERROR: No matching targets found.')

    @responses.activate
    def test_share_dataproduct_valid_target_found(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"results": [{'id': 1}]},
            status=200
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )
        responses.add(
            responses.POST,
            destination_tom_base_url + 'api/dataproducts/',
            json={"message": "Data product successfully uploaded."},
            status=200,
        )

        response = self.client.post(
            reverse('dataproducts:share', kwargs={'dp_pk': self.data_product.id}),
            {
                'share_authors': ['test_author'],
                'target': self.target.id,
                'submitter': ['test_submitter'],
                'share_destination': [share_destination],
                'share_title': ['Updated data for thingy.'],
                'share_message': ['test_message']
            },
            follow=True
        )
        self.assertContains(response, 'Data product successfully uploaded.')

    @responses.activate
    def test_share_reduceddatums_target_valid_responses(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"results": [{'id': 1}]},
            status=200
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )
        responses.add(
            responses.POST,
            destination_tom_base_url + 'api/reduceddatums/',
            json={},
            status=201,
        )

        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            {
                'share_authors': ['test_author'],
                'target': self.target.id,
                'submitter': ['test_submitter'],
                'share_destination': [share_destination],
                'share_title': ['Updated data for thingy.'],
                'share_message': ['test_message']
            },
            follow=True
        )
        self.assertContains(response, '3 of 3 datums successfully saved.')

    @responses.activate
    def test_share_reduced_datums_valid_responses(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"results": [{'id': 1}]},
            status=200
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )
        responses.add(
            responses.POST,
            destination_tom_base_url + 'api/reduceddatums/',
            json={},
            status=201,
        )

        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            {
                'share_authors': ['test_author'],
                'target': self.target.id,
                'submitter': ['test_submitter'],
                'share_destination': [share_destination],
                'share_title': ['Updated data for thingy.'],
                'share_message': ['test_message'],
                'share-box': [1, 2]
            },
            follow=True
        )
        self.assertContains(response, '2 of 2 datums successfully saved.')

    @responses.activate
    def test_share_reduced_datums_invalid_responses(self):
        share_destination = 'local_host'
        destination_tom_base_url = settings.DATA_SHARING[share_destination]['BASE_URL']

        rsp1 = responses.Response(
            method="GET",
            url=destination_tom_base_url + 'api/targets/',
            json={"results": [{'id': 1}]},
            status=200
        )
        responses.add(rsp1)
        responses.add(
            responses.GET,
            "http://hermes-dev.lco.global/api/v0/profile/",
            json={"error": "not found"},
            status=404,
        )

        sharing_dict = {
            'share_authors': ['test_author'],
            'target': self.target.id,
            'submitter': ['test_submitter'],
            'share_destination': [share_destination],
            'share_title': ['Updated data for thingy.'],
            'share_message': ['test_message'],
            'share-box': [1, 2]
        }
        # Check 500 error
        responses.add(
            responses.POST,
            destination_tom_base_url + 'api/reduceddatums/',
            json={},
            status=500,
        )
        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            sharing_dict,
            follow=True
        )
        self.assertContains(response, 'No valid data shared. These data may already exist in target TOM.')

        # Check 400 error
        responses.add(
            responses.POST,
            destination_tom_base_url + 'api/reduceddatums/',
            json={},
            status=400,
        )
        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            sharing_dict,
            follow=True
        )
        self.assertContains(response, 'No valid data shared. These data may already exist in target TOM.')

        # Check 300 error
        responses.add(
            responses.POST,
            destination_tom_base_url + 'api/reduceddatums/',
            json={},
            status=300,
        )
        response = self.client.post(
            reverse('dataproducts:share_all', kwargs={'tg_pk': self.target.id}),
            sharing_dict,
            follow=True
        )
        self.assertContains(response, 'No valid data shared. These data may already exist in target TOM.')
