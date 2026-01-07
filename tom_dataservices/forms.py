from django import forms
from crispy_forms.helper import FormHelper

from tom_dataservices.models import DataServiceQuery


class BaseQueryForm(forms.Form):
    """
    Form class representing the default form for a dataservice.
    """
    query_save = forms.BooleanField(
        required=False,
        initial=False,
        label="Save Query")
    query_name = forms.CharField(
        required=False)
    data_service = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        # self.helper['query_save'].wrap(Field, type='hidden')

    def save(self, query_id=None):
        """
        Saves the form data as a DataServiceQuery object

        :returns: The query object.
        :rtype: dict
        """
        if query_id:
            query = DataServiceQuery.objects.get(id=query_id)
        else:
            query = DataServiceQuery()
        query.name = self.cleaned_data['query_name']
        query.data_service = self.cleaned_data['data_service']
        query.parameters = self.cleaned_data
        query.save()
        return query
