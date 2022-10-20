from django import forms
from django.contrib.auth.models import Group
from django.conf import settings

from tom_dataproducts.models import DataProductGroup, DataProduct
from tom_observations.models import ObservationRecord
from tom_targets.models import Target


DESTINATION_OPTIONS = (('hermes', 'Hermes'),
                       ('tom-demo-dev', '2nd best TOM'),
                       ('local_host', 'Best TOM (My TOM)'))


class AddProductToGroupForm(forms.Form):
    products = forms.ModelMultipleChoiceField(
        DataProduct.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )
    group = forms.ModelChoiceField(DataProductGroup.objects.all())


class DataProductUploadForm(forms.Form):
    observation_record = forms.ModelChoiceField(
        ObservationRecord.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    files = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={'multiple': True}
        )
    )
    data_product_type = forms.ChoiceField(
        choices=[v for k, v in settings.DATA_PRODUCT_TYPES.items()],
        widget=forms.RadioSelect(),
        required=True
    )
    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.TARGET_PERMISSIONS_ONLY:
            self.fields['groups'] = forms.ModelMultipleChoiceField(Group.objects.none(),
                                                                   required=False,
                                                                   widget=forms.CheckboxSelectMultiple)


class DataProductShareForm(forms.Form):
    share_destination = forms.ChoiceField(required=True, choices=DESTINATION_OPTIONS, label="Destination")
    share_title = forms.CharField(required=False, label="Title")
    share_message = forms.CharField(required=False, label="Message", widget=forms.Textarea())
    share_authors = forms.CharField(required=False, widget=forms.HiddenInput())
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False)
    submitter = forms.CharField(
        widget=forms.HiddenInput()
    )
