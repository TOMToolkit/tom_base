from django import forms
from django.apps import apps
from django.db.models.fields import Field

from tom_publications.models import LatexConfiguration


class LatexTableForm(forms.Form):

    # field_list_models = {
    #     'targetlist': 'target',
    #     'observationgroup': 'observationrecord'
    # }

    model_pk = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True
    )
    model_name = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    template = forms.CharField(widget=forms.HiddenInput(), required=False)
    save = forms.BooleanField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        """
        Determines the model name for which to generate a latex form, and uses it to get the possible model fields to
        provide as options. Tries to get the values from args first (in the case of a bound form), and initial second.
        """
        print('init')
        print(args)
        print(kwargs)

        model_name = None
        field_list = None
        if args:
            model_name = args[0].get('model_name')
            field_list = args[0].get('field_list')

        if not model_name:
            model_name = kwargs.get('initial', {}).get('model_name')
        if not field_list:
            field_list = kwargs.get('initial', {}).get('field_list', [])

        super().__init__(*args, **kwargs)

        for app in apps.get_app_configs():
            try:
                # model = app.get_model(self.field_list_models[model_name])
                model = app.get_model(model_name)
                break
            except LookupError:
                pass


        print(model)
        self.fields['field_list'] = forms.MultipleChoiceField(
            choices=[(v.name, v.name) for v in model._meta.get_fields() if issubclass(type(v), Field)],
            initial=field_list,
            widget=forms.CheckboxSelectMultiple(),
            required=True,
        )


class LatexConfigurationForm(forms.ModelForm):
    class Meta:
        model = LatexConfiguration
        fields = '__all__'
