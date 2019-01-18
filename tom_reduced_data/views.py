from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django_filters.views import FilterView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import call_command

from .models import ReducedDataGrouping, ReducedDatum


class ReducedDataGroupingListView(LoginRequiredMixin, FilterView):
    template_name = 'tom_reduced_data/reduced_data_list.html'
    model = ReducedDataGrouping


class ReducedDataGroupingView(DetailView):
    model = ReducedDataGrouping


class UpdateReducedDataGroupingView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        grouping_id = kwargs.get('pk', None)
        target_id = request.GET.get('target_id', None)
        try:
            rdg = ReducedDataGrouping.objects.get(id=grouping_id)
            target = Target.objects.get(id=target_id)
        except ObjectDoesNotExist:
            pass
        call_command('update_reduced_data', target_id)