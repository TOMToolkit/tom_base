import factory
import json
import random

from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.models import ObservationRecord
from tom_targets.models import Target, TargetExtra, TargetList, TargetName


class TargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    name = factory.Sequence(lambda n: f'perf_target_{n}')
    type = 'SIDEREAL'
    ra = factory.Faker('pyfloat')
    dec = factory.Faker('pyfloat')
    epoch = factory.Faker('pyfloat')
    pm_ra = factory.Faker('pyfloat')
    pm_dec = factory.Faker('pyfloat')


class TargetExtraFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetExtra

    key = factory.Sequence(lambda k: f'key{k}')
    value = factory.Faker('pystr')


class TargetListFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetList

    name = factory.Sequence(lambda p: f'perf_list{p}')


class TargetNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetName

    name = factory.Sequence(lambda l: f'name{l}')


class ObservingRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObservationRecord

    facility = 'LCO'
    observation_id = factory.Faker('pydecimal', right_digits=0, left_digits=7)
    status = factory.Iterator(['PENDING', 'COMPLETED', 'WINDOW_EXPIRED'])
    parameters = json.dumps({
        'facility': 'LCO',
        'target_id': random.randint(0, 1000),
        'observation_type': 'IMAGING',
        'name': 'With Perms',
        'ipp_value': 1.05,
        'start': '2020-03-01 00:00:00',
        'end': '2020-03-02 00:00:00',
        'exposure_count': 1,
        'exposure_time': 2.0,
        'max_airmass': 4.0,
        'observation_mode': 'NORMAL',
        'proposal': 'LCOSchedulerTest',
        'filter': 'I',
        'instrument_type': '1M0-SCICAM-SINISTRO'
    })


class DataProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataProduct


class PhotometryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReducedDatum

    data_type = 'photometry'
    timestamp = factory.Faker('date_time_this_year')
    value = json.dumps({
        'magnitude': random.randint(16, 25),
        'filter': 'i',
        'error': random.random()
    })


# class SpectrumFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = DataProduct
