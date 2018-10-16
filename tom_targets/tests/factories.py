import factory

from tom_targets.models import Target


class SiderealTargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    identifier = factory.Faker('pystr')
    name = factory.Faker('pystr')
    type = Target.SIDEREAL
    ra = factory.Faker('pyfloat')
    dec = factory.Faker('pyfloat')
    epoch = factory.Faker('pyfloat')
    pm_ra = factory.Faker('pyfloat')
    pm_dec = factory.Faker('pyfloat')


class NonSiderealTargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    identifier = factory.Faker('pystr')
    name = factory.Faker('pystr')
    type = Target.NON_SIDEREAL
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
