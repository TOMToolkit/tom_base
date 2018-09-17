from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic import TemplateView
from django_filters.views import FilterView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages

from .models import Target
from .forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset
from .import_targets import import_targets
from tom_observations.facility import get_service_classes


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


class TargetDetail(DetailView):
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['facilities'] = get_service_classes()
        return context

    model = Target
    fields = '__all__'


class TargetImport(TemplateView):
    template_name = 'tom_targets/target_import.html'

    def post(self, request):
        csv_file = request.FILES['target_csv']
        result = import_targets(csv_file)
        messages.success(request, 'Targets created: {}'.format(len(result['targets'])))
        for error in result['errors']:
            messages.warning(request, error)
        return redirect(reverse('tom_targets:list'))
