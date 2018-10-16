import factory

from django.conf import settings

from tom_targets.models import Target
from tom_observations.models import ObservationRecord

class TargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    identifier = factory.Faker('pystr')
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
