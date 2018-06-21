from django.views.generic.edit import FormView
from django.urls import reverse
from urllib.parse import urlencode

from .forms import CatalogQueryForm


class CatalogQueryView(FormView):
    form_class = CatalogQueryForm
    template_name = 'tom_catalogs/query_form.html'

    def form_valid(self, form):
        self.target = form.get_target()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('targets:create') + '?' + urlencode(self.target.as_dict())
