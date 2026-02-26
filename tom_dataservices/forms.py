from django import forms
from django.urls import reverse
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Column, Layout, Row, Submit

from tom_dataservices.models import DataServiceQuery
from tom_dataservices.dataservices import get_data_service_classes
from tom_targets.models import Target


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
        self.helper.layout = self.get_layout()

    def get_layout(self):
        exclude = ["query_save", "query_name"]
        field_keys = [f for f in self.fields.keys() if f not in exclude]
        return Layout(*field_keys)

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


class UpdateDataFromDataServiceForm(forms.Form):
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    data_service = forms.ChoiceField(required=True, choices=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data_service_list = get_data_service_classes()
        data_service_choices = []
        for name, data_service in data_service_list.items():
            if hasattr(data_service, 'build_query_parameters_from_target'):
                data_service_choices.append((name, name))
        self.fields['data_service'].choices = data_service_choices
        self.helper = FormHelper()
        self.helper.form_action = reverse('tom_dataservices:update-data')
        self.helper.layout = Layout(
            'target',
            Row(
                Column(
                    'data_service'
                    ),
                Column(
                    ButtonHolder(
                        Submit('Update', 'Update Reduced Data'), css_class="bottom"
                        )
                    ),
                )
        )
