import re
import json

from astropy.time import Time
from datetime import datetime
from .models import ReducedDatum
from django.conf import settings


def process_data_product(data_product, target):
    if data_product.tag == 'photometry':
        with open(settings.MEDIA_ROOT + '/' + str(data_product.data)) as f:
            data = f.readlines()
            for line in data:
                #TODO: Make processing separator- and column-ordering-agnostic
                photometry_datum = [datum.strip() for datum in re.split(',', line)]
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
        with open(settings.MEDIA_ROOT + '/' + str(data_product.data)) as f:
            data = f.readlines()
            spectrum = {}
            index = 0
            for line in data:
                spectral_sample = [sample.strip() for sample in re.split('[\s,|;]', line)]
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
