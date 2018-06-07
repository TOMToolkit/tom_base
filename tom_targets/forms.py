from django.forms import ModelForm
from django.conf import settings
from .models import Target

class SiderealTargetCreateForm(ModelForm):
    class Meta:
        model = Target
        fields = settings.SIDEREAL_FIELDS

class NonSiderealTargetCreateForm(ModelForm):
    class Meta:
        model = Target
        fields = settings.NON_SIDEREAL_FIELDS