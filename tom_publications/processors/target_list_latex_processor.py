import io

from astropy.io import ascii
from astropy.table import Table
from crispy_forms.bootstrap import InlineCheckboxes
from crispy_forms.layout import Div, Layout
from django import forms
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Field

from tom_publications.latex import GenericLatexProcessor, GenericLatexForm
from tom_publications.forms import LatexTableForm
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
            self.layout()
        )

    def layout(self):
        return Div(Div(InlineCheckboxes('field_list')))
        # print(len(self.fields['field_list']))


class TargetListLatexProcessor(GenericLatexProcessor):

    form_class = TargetListLatexForm

    def get_form(self, data=None, **kwargs):
        return self.form_class(data, **kwargs)

    def create_latex(self, pk, field_names):
        # TODO: allow specification of a header
        # TODO: allow addition of notes and references
        target_list = TargetList.objects.get(pk=pk)
        targets = target_list.targets

        table_data = {}
        print(field_names)
        for field in field_names:
            for target in target_list.targets.all():
                try:
                    verbose_name = Target._meta.get_field(field).verbose_name
                    table_data.setdefault(verbose_name, []).append(getattr(target, field))
                except FieldDoesNotExist:
                    table_data.setdefault(field, []).append(TargetExtra.objects.filter(target=target, key=field).first().value)

        latex = io.StringIO()
        ascii.write(table_data, latex, format='latex')
        print(latex.getvalue())
        return latex.getvalue()
