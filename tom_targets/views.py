from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from .models import Target, TargetList
from .forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm


class TargetList(ListView):
    model = Target


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