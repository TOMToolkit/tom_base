import factory
import json

from tom_targets.models import Target, TargetName
from tom_observations.models import ObservationRecord, ObservingStrategy


class TargetNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetName

    name = factory.Faker('pystr')


class TargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    name = factory.Faker('pystr')
    ra = factory.Faker('pyfloat')
    dec = factory.Faker('pyfloat')
    epoch = factory.Faker('pyfloat')
    pm_ra = factory.Faker('pyfloat')
    pm_dec = factory.Faker('pyfloat')


class ObservingRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObservationRecord

    target = factory.RelatedFactory(TargetFactory)
    facility = 'LCO'
    observation_id = factory.Faker('pydecimal', right_digits=0, left_digits=7)
    status = 'PENDING'
    parameters = json.dumps({
        'facility': 'LCO',
        'target_id': 1,
        'observation_type': 'IMAGING',
        'name': 'With Perms',
        'ipp_value': 1.05,
        'start': '2020-01-01T00:00:00',
        'end': '2020-01-02T00:00:00',
        'exposure_count': 1,
        'exposure_time': 2.0,
        'max_airmass': 4.0,
        'observation_mode': 'NORMAL',
        'proposal': 'LCOSchedulerTest',
        'filter': 'I',
        'instrument_type': '1M0-SCICAM-SINISTRO'
    })


class ObservingStrategyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObservingStrategy

    facility = 'LCO'
    parameters = json.dumps({
        'facility': 'LCO',
        'target_id': 1,
        'observation_type': 'IMAGING',
        'name': 'With Perms',
        'ipp_value': 1.05,
        'start': '2020-01-01T00:00:00',
        'end': '2020-01-02T00:00:00',
        'exposure_count': 1,
        'exposure_time': 2.0,
        'max_airmass': 4.0,
        'observation_mode': 'NORMAL',
        'proposal': 'LCOSchedulerTest',
        'filter': 'I',
        'instrument_type': '1M0-SCICAM-SINISTRO'
    })
