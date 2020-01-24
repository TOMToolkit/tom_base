import io

from astropy.io import ascii
from astropy.table import Table

from tom_publications.latex import GenericLatexProcessor
from tom_targets.models import Target


class TargetLatexProcessor(GenericLatexProcessor):

    def create_latex(self, pk, field_names):
        target = Target.objects.get(pk=pk)

        table_data = {}
        print(field_names)
        for field in field_names:
            table_data.setdefault(field, []).append(getattr(target, field))

        latex = io.StringIO()
        ascii.write(table_data, latex, format='latex')
        print(latex.getvalue())
        return latex.getvalue()
