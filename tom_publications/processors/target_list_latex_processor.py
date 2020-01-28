import io

from astropy.io import ascii
from astropy.table import Table
from django import forms
from django.db.models import Field

from tom_publications.latex import GenericLatexProcessor, GenericLatexForm
from tom_publications.forms import LatexTableForm
from tom_targets.models import Target, TargetList


class TargetListLatexForm(LatexTableForm):
    field_list = forms.MultipleChoiceField(
        choices=[(v.name, v.name) for v in Target._meta.get_fields() if issubclass(type(v), Field)],
        required=True,
        widget=forms.CheckboxSelectMultiple()
    )


class TargetListLatexProcessor(GenericLatexProcessor):

    form_class = TargetListLatexForm

    def get_form(self, data=None, **kwargs):
        print(kwargs)
        return self.form_class(data, **kwargs)

    def create_latex(self, pk, field_names):
        target_list = TargetList.objects.get(pk=pk)
        targets = target_list.targets

        table_data = {}
        print(field_names)
        for field in field_names:
            for target in target_list.targets.all():
                table_data.setdefault(field, []).append(getattr(target, field))

        latex = io.StringIO()
        ascii.write(table_data, latex, format='latex')
        print(latex.getvalue())
        return latex.getvalue()
