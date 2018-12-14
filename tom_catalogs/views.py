from django.views.generic.edit import FormView
from django.urls import reverse
from urllib.parse import urlencode
from django.core.exceptions import ValidationError

from .forms import CatalogQueryForm
from .harvester import MissingDataException


class CatalogQueryView(FormView):
    form_class = CatalogQueryForm
    template_name = 'tom_catalogs/query_form.html'

    def form_valid(self, form):
        try:
            self.target = form.get_target()
        except MissingDataException:
            form.add_error('term', ValidationError('Object not found'))
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'targets:create') + '?' + urlencode(self.target.as_dict()
        )
