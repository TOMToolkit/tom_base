from crispy_forms.bootstrap import InlineCheckboxes
from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Field

from tom_publications.latex import GenericLatexProcessor, GenericLatexForm
from tom_observations.models import ObservationRecord, ObservationGroup


class ObservationGroupLatexForm(GenericLatexForm):
    field_list = forms.MultipleChoiceField(
        choices=[(v.name, v.verbose_name) for v in ObservationRecord._meta.get_fields() if issubclass(type(v), Field)],
        required=True,
        widget=forms.CheckboxSelectMultiple()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            InlineCheckboxes('field_list')
        )


class ObservationGroupLatexProcessor(GenericLatexProcessor):

    form_class = ObservationGroupLatexForm

    def create_latex_table_data(self, cleaned_data):
        # TODO: enable user to modify column header
        # TODO: add preview PDF
        observation_group = ObservationGroup.objects.get(pk=cleaned_data.get('model_pk'))

        table_data = {}
        for field in cleaned_data.get('field_list', []):
            for obs_record in observation_group.observation_records.all():
                try:
                    verbose_name = ObservationRecord._meta.get_field(field).verbose_name
                    table_data.setdefault(verbose_name, []).append(getattr(obs_record, field))
                except FieldDoesNotExist:
                    pass

        return table_data
