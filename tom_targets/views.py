from io import StringIO
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic import TemplateView, View
from django_filters.views import FilterView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.http import HttpResponse
from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from dateutil.parser import parse

import plotly
from plotly import offline, io
import plotly.graph_objs as go

from .models import Target
from .forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset, TargetVisibilityForm
from .import_targets import import_targets
from .filters import TargetFilter
from tom_observations.facility import get_service_classes


class TargetListView(FilterView):
    template_name = 'tom_targets/target_list.html'
    paginate_by = 25
    strict = False
    model = Target
    filterset_class = TargetFilter


class TargetCreate(LoginRequiredMixin, CreateView):
    model = Target
    fields = '__all__'

    def get_default_target_type(self):
        try:
            return settings.TARGET_TYPE
        except AttributeError:
            return Target.SIDEREAL

    def get_initial(self):
        return {'type': self.get_default_target_type(), **dict(self.request.GET.items())}

    def get_context_data(self, **kwargs):
        context = super(TargetCreate, self).get_context_data(**kwargs)
        context['type_choices'] = Target.TARGET_TYPES
        context['extra_form'] = TargetExtraFormset()
        return context

    def get_form_class(self):
        target_type = self.get_default_target_type()
        if self.request.GET:
            target_type = self.request.GET.get('type', target_type)
        elif self.request.POST:
            target_type = self.request.POST.get('type', target_type)
        if target_type == Target.SIDEREAL:
            self.initial['type'] = Target.SIDEREAL
            return SiderealTargetCreateForm
        elif target_type == Target.NON_SIDEREAL:
            self.initial['type'] = Target.NON_SIDEREAL
            return NonSiderealTargetCreateForm

    def form_valid(self, form):
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST)
        if extra.is_valid():
            extra.instance = self.object
            extra.save()
        return redirect(self.get_success_url())


class TargetUpdate(LoginRequiredMixin, UpdateView):
    model = Target
    fields = '__all__'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['extra_form'] = TargetExtraFormset(instance=self.object)
        return context

    def form_valid(self, form):
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST, instance=self.object)
        if extra.is_valid():
            extra.save()
        return redirect(self.get_success_url())


class TargetDelete(LoginRequiredMixin, DeleteView):
    success_url = reverse_lazy('targets:list')
    model = Target


class TargetDetail(DetailView):
    model = Target

    def get_airmass_plot(self):
        start_time = parse(self.request.GET['start_time'])
        end_time = parse(self.request.GET['end_time'])
        if self.request.GET.get('airmass'):
            airmass_limit = float(self.request.GET['airmass'])
        else:
            airmass_limit = None
        visibility_data = self.object.get_visibility(start_time, end_time, 10, airmass_limit)
        plot_data = [go.Scatter(x=data[0], y=data[1], mode='lines', name=site) for site, data in visibility_data.items()]
        layout = go.Layout(yaxis=dict(autorange='reversed'))
        return offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['facilities'] = get_service_classes()
        context['form'] = TargetVisibilityForm()
        if all(self.request.GET.get(x) for x in ['start_time', 'end_time']):
            context['form'] = TargetVisibilityForm({
                'start_time': self.request.GET.get('start_time'),
                'end_time': self.request.GET.get('end_time'),
                'airmass': self.request.GET.get('airmass')
            })
            if context['form'].is_valid():
                context['visibility_graph'] = self.get_airmass_plot()
        return context

    def get(self, request, *args, **kwargs):
        update_status = request.GET.get('update_status', False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            target_id = kwargs.get('pk', None)
            out = StringIO()
            call_command('updatestatus', target_id=target_id, stdout=out)
            messages.info(request, out.getvalue())
            return redirect(reverse('tom_targets:detail', args=(target_id,)))
        return super().get(request, *args, **kwargs)


class TargetImport(LoginRequiredMixin, TemplateView):
    template_name = 'tom_targets/target_import.html'

    def post(self, request):
        csv_file = request.FILES['target_csv']
        result = import_targets(csv_file)
        messages.success(request, 'Targets created: {}'.format(len(result['targets'])))
        for error in result['errors']:
            messages.warning(request, error)
        return redirect(reverse('tom_targets:list'))
