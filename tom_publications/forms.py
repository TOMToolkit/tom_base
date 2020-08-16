from django import forms

from tom_publications.models import LatexConfiguration


class LatexTableForm(forms.Form):

    model_pk = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True
    )
    model_name = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    template = forms.CharField(widget=forms.HiddenInput(), required=False)
