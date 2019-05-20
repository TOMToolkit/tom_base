import json
import os
import re
import shutil

from astropy.io import fits
from astropy.time import Time
from datetime import datetime
from django.conf import settings
from django.core.files import File

from .models import ReducedDatum, DataProduct

def process_data_product(data_product, target):
    if data_product.tag == 'photometry':
        with data_product.data.file.open() as f:
            for line in f:
                #TODO: Make processing separator- and column-ordering-agnostic
                photometry_datum = [datum.strip() for datum in re.split(',', line.decode('UTF-8'))]
                time = Time(float(photometry_datum[0]), format='mjd')
                time.format = 'datetime'
                value = {
                    'magnitude': photometry_datum[2],
                    'filter': photometry_datum[1],
                    'error': photometry_datum[3]
                }
                ReducedDatum.objects.create(
                    target=target,
                    data_product=data_product,
                    data_type=data_product.tag,
                    timestamp=time.value,
                    value=json.dumps(value)
                )
    elif data_product.tag == 'spectroscopy':
        spectrum = {}
        index = 0
        with data_product.data.file.open() as f:
            for line in f:
                spectral_sample = [sample.strip() for sample in re.split('[\s,|;]', line.decode('UTF-8'))]
                spectrum[str(index)] = ({
                    'wavelength': spectral_sample[0],
                    'flux': spectral_sample[1]
                })
                index += 1
        ReducedDatum.objects.create(
            target=target,
            data_product=data_product,
            data_type=data_product.tag,
            timestamp=datetime.now(),
            value=json.dumps(spectrum)
        )

def create_image_dataproduct(data_product):
    tmpfile = data_product.create_thumbnail()
    if tmpfile:
        dp, created = DataProduct.objects.get_or_create(
            product_id="{}_{}".format(data_product.product_id, "jpeg"),
            target=data_product.target,
            observation_record=data_product.observation_record,
            tag='image_file',
        )
        outfile_name = os.path.basename(data_product.data.file.name)
        filename = outfile_name.split(".")[0] + ".jpg"
        with open(tmpfile.name, 'rb') as f:
            dp.data.save(filename, File(f), save=True)
            dp.save()
        tmpfile.close()
        return True

    return

def find_img_size(filename):
    try:
        return settings.THUMBNAIL_MAX_SIZE
    except:
        hdul = fits.open(filename)
        xsize = 0
        ysize = 0
        for hdu in hdul:
            try:
                xsize = max(xsize,hdu.header['NAXIS1'])
                ysize = max(ysize,hdu.header['NAXIS2'])
            except KeyError:
                pass
        return (xsize, ysize)
