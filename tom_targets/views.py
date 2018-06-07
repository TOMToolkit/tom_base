from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from .models import Target, TargetList


class TargetList(ListView):
    model = Target


class TargetCreate(CreateView):
    model = Target
    fields = '__all__'


class TargetUpdate(UpdateView):
    model = Target
    fields = '__all__'


class TargetDelete(DeleteView):
    model = Target


class TargetDetail(DetailView):
    model = Target