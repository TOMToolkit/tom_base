import factory

from tom_targets.models import Target, TargetName
from tom_observations.models import ObservationRecord, ObservationTemplate


class TargetNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetName

    name = factory.Faker('pystr')


class SiderealTargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    name = factory.Faker('pystr')
    type = Target.SIDEREAL
    ra = factory.Faker('pyfloat', min_value=-90, max_value=90)
    dec = factory.Faker('pyfloat', min_value=-90, max_value=90)
    epoch = factory.Faker('pyfloat')
    pm_ra = factory.Faker('pyfloat')
    pm_dec = factory.Faker('pyfloat')


class NonSiderealTargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    name = factory.Faker('pystr')
    type = Target.NON_SIDEREAL
    scheme = factory.Faker('random_element', elements=[s[0] for s in Target.TARGET_SCHEMES])
    mean_anomaly = factory.Faker('pyfloat')
    arg_of_perihelion = factory.Faker('pyfloat')
    lng_asc_node = factory.Faker('pyfloat')
    inclination = factory.Faker('pyfloat')
    mean_daily_motion = factory.Faker('pyfloat')
    semimajor_axis = factory.Faker('pyfloat')
    ephemeris_period = factory.Faker('pyfloat')
    ephemeris_period_err = factory.Faker('pyfloat')
    ephemeris_epoch = factory.Faker('pyfloat')
    ephemeris_epoch_err = factory.Faker('pyfloat')


class ObservingRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObservationRecord

    target = factory.RelatedFactory(SiderealTargetFactory)
    facility = 'LCO'
    observation_id = factory.Faker('pydecimal', right_digits=0, left_digits=7)
    status = 'PENDING'
    parameters = {
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
    }


class ObservationTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObservationTemplate

    facility = 'LCO'
    parameters = {
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
    }
