from django.forms
from .models import Target

class SiderealTargetCreateForm(ModelForm):
    class Meta:
        model = Target
        fields = '__all__'

class NonSiderealTargetCreateForm(ModelForm):
    class Meta:
        model = Target
        fields = '__all__'