from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django_filters.views import FilterView
from django.views.generic.list import ListView
from django.urls import reverse

from .models import Target, TargetList
from .forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm


class TargetListView(FilterView):
    template_name = 'tom_targets/target_list.html'
    paginate_by = 25
    model = Target
    filter_fields = ['type', 'identifier', 'name', 'designation']


class TargetCreate(CreateView):
    model = Target
    fields = '__all__'
    success_url = reverse('targets:list')

    def get_context_data(self, **kwargs):
        context = super(TargetCreate, self).get_context_data(**kwargs)
        context['type_choices'] = ['sidereal', 'non_sidereal']
        return context

    def get_form_class(self):
        if self.request.GET['type'] == 'sidereal':
            return SiderealTargetCreateForm
        elif self.request.GET['type'] ==  'non_sidereal':
            return NonSiderealTargetCreateForm
        return self.form_class


class TargetUpdate(UpdateView):
    model = Target
    fields = '__all__'


class TargetDelete(DeleteView):
    model = Target


class TargetDetail(DetailView):
    model = Target
