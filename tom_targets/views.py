from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django_filters.views import FilterView

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

    def get_form_class(self):
        if self.kwargs['type'] == 'sidereal':
            return SiderealTargetCreateForm()
        elif self.kwargs['type'] ==  'non_sidereal':
            return NonSiderealTargetCreateForm()
        return self.form_class


class TargetUpdate(UpdateView):
    model = Target
    fields = '__all__'


class TargetDelete(DeleteView):
    model = Target


class TargetDetail(DetailView):
    model = Target
