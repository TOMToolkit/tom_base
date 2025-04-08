from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class BaseQueryForm(forms.Form):
    """
    Form class representing the default form for a dataservice.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Submit'))
