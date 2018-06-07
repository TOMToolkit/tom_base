from django.forms import ModelForm
from .models import Target

class SiderealTargetCreateForm(ModelForm):
    class Meta:
        model = Target
        fields = '__all__'

class NonSiderealTargetCreateForm(ModelForm):
    class Meta:
        model = Target
        fields = '__all__'