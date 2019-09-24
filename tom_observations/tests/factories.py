import factory

from tom_targets.models import Target, TargetName
from tom_observations.models import ObservationRecord


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
    status = factory.Faker('pystr')
