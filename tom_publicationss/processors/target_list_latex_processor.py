from crispy_forms.bootstrap import InlineCheckboxes
from crispy_forms.layout import Layout
from django import forms
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Field

from tom_publications.latex import GenericLatexProcessor, GenericLatexForm
from tom_targets.models import Target, TargetExtra, TargetList


class TargetListLatexForm(GenericLatexForm):
    field_list = forms.MultipleChoiceField(
        choices=[(v.name, v.verbose_name) for v in Target._meta.get_fields()
                 if issubclass(type(v), Field)] + [(e['name'], e['name']) for e in settings.EXTRA_FIELDS],
        required=True,
        widget=forms.CheckboxSelectMultiple()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            InlineCheckboxes('field_list')
        )


class TargetListLatexProcessor(GenericLatexProcessor):

    form_class = TargetListLatexForm

    def create_latex_table_data(self, cleaned_data):
        # TODO: enable user to modify column header
        # TODO: add preview PDF
        target_list = TargetList.objects.get(pk=cleaned_data.get('model_pk'))

        table_data = {}
        for field in cleaned_data.get('field_list', []):
            for target in target_list.targets.all():
                try:
                    verbose_name = Target._meta.get_field(field).verbose_name
                    table_data.setdefault(verbose_name, []).append(getattr(target, field))
                except FieldDoesNotExist:
                    table_data.setdefault(field, []).append(TargetExtra.objects.filter(target=target,
                                                                                       key=field).first().value)

        return table_data
