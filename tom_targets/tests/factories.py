import factory

from tom_targets.models import Target, TargetName, TargetList, TargetExtra


class TargetExtraFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetExtra

    key = factory.Faker('pystr')
    value = factory.Faker('pystr')


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

    targetextra_set = factory.RelatedFactoryList(TargetExtraFactory, factory_related_name='target', size=3)
    aliases = factory.RelatedFactoryList(TargetNameFactory, factory_related_name='target', size=2)


class NonSiderealTargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

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

    targetextra_set = factory.RelatedFactoryList(TargetExtraFactory, factory_related_name='target', size=3)
    aliases = factory.RelatedFactoryList(TargetNameFactory, factory_related_name='target', size=2)


class TargetGroupingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetList
    name = factory.Faker('pystr')
