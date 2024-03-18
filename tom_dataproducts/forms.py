from django import forms
from django.contrib.auth.models import Group
from django.conf import settings

from tom_dataproducts.models import DataProductGroup, DataProduct, DATA_TYPE_CHOICES
from tom_observations.models import ObservationRecord
from tom_targets.models import Target
from tom_dataproducts.sharing import get_sharing_destination_options


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
        widget=forms.ClearableFileInput()
    )
    data_product_type = forms.ChoiceField(
        choices=DATA_TYPE_CHOICES,
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


class DataShareForm(forms.Form):
    share_destination = forms.ChoiceField(required=True, choices=[], label="Destination")
    share_title = forms.CharField(required=False, label="Title")
    share_message = forms.CharField(required=False, label="Message", widget=forms.Textarea(attrs={'rows': 4}))
    share_authors = forms.CharField(required=False, widget=forms.HiddenInput())
    data_type = forms.ChoiceField(required=False, choices=DATA_TYPE_CHOICES, label="Data Type")
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False)
    submitter = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['share_destination'].choices = get_sharing_destination_options()
