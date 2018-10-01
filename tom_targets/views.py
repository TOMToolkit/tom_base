from io import StringIO
from datetime import datetime, timedelta, timezone

from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView, FormMixin
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic import TemplateView, View
from django_filters.views import FilterView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.core.management import call_command

from .models import Target
from .forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset, TargetVisibilityForm
from .import_targets import import_targets
from tom_observations.facility import get_service_classes
from tom_observations.models import ObservationRecord


class TargetListView(FilterView):
    template_name = 'tom_targets/target_list.html'
    paginate_by = 25
    model = Target
    filterset_fields = ['type', 'identifier', 'name', 'designation']


class TargetCreate(CreateView):
    model = Target
    fields = '__all__'

    def get_default_target_type(self):
        try:
            return settings.DEFAULT_TARGET_TYPE
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


class TargetUpdate(UpdateView):
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


class TargetDelete(DeleteView):
    success_url = reverse_lazy('targets:list')
    model = Target


class TargetDisplay(DetailView):
    model = Target
    fields = '__all__'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['facilities'] = get_service_classes()
        context['form'] = TargetVisibilityForm()
        return context

    def get(self, request, *args, **kwargs):
        update_status = request.GET.get('update_status', False)
        if update_status:
            target_id = kwargs.get('pk', None)
            out = StringIO()
            call_command('updatestatus', target_id=target_id, stdout=out)
            messages.info(request, out.getvalue())
            return redirect(reverse('tom_targets:detail', args=(target_id,)))
        return super().get(request, *args, **kwargs)


class TargetObservationPlan(SingleObjectMixin, FormView):
    template_name = 'tom_targets/target_detail.html'
    form_class = TargetVisibilityForm
    model = Target

    def get_success_url(self):
        return reverse('tom_targets:detail', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        print('post')
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        print('form invalid')
        print(errors)
        return super().form_invalid(form)

    def form_valid(self, form):
        print('form valid')
        print(form.cleaned_data)
        print(self.request)
        start_time = form.cleaned_data['start_time']
        end_time = form.cleaned_data['end_time']
        self.object.get_visibility(start_time, end_time, 10)
        return super().form_valid(form)


class TargetDetail(View):
    def get(self, request, *args, **kwargs):
        view = TargetDisplay.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = TargetObservationPlan.as_view()
        return view(request, *args, **kwargs)


class TargetImport(TemplateView):
    template_name = 'tom_targets/target_import.html'

    def post(self, request):
        csv_file = request.FILES['target_csv']
        result = import_targets(csv_file)
        messages.success(request, 'Targets created: {}'.format(len(result['targets'])))
        for error in result['errors']:
            messages.warning(request, error)
        return redirect(reverse('tom_targets:list'))
