from io import StringIO
import django_filters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView
from django_filters.views import FilterView
from django.views.generic.detail import DetailView
from django.urls import reverse
from django.shortcuts import redirect
from django.core.management import call_command
from django.contrib import messages
from guardian.shortcuts import get_objects_for_user

from .models import ObservationRecord
from .forms import ManualObservationForm
from tom_dataproducts.forms import AddProductToGroupForm
from tom_targets.models import Target
from tom_observations.facility import get_service_class


class ObservationFilter(django_filters.FilterSet):
    ordering = django_filters.OrderingFilter(
        fields=['scheduled_start', 'scheduled_end', 'status', 'created', 'modified']
    )
    scheduled_start = django_filters.DateTimeFromToRangeFilter()
    scheduled_end = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = ObservationRecord
        fields = ['ordering', 'observation_id', 'target_id', 'facility', 'status']


class ObservationListView(FilterView):
    filterset_class = ObservationFilter
    template_name = 'tom_observations/observation_list.html'
    paginate_by = 25
    model = ObservationRecord
    strict = False

    def get_queryset(self, *args, **kwargs):
        return ObservationRecord.objects.filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        )

    def get(self, request, *args, **kwargs):
        update_status = request.GET.get('update_status', False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            out = StringIO()
            call_command('updatestatus', stdout=out)
            messages.info(request, out.getvalue())
            return redirect(reverse('tom_observations:list'))
        return super().get(request, *args, **kwargs)


class ObservationCreateView(LoginRequiredMixin, FormView):
    template_name = 'tom_observations/observation_form.html'

    def get_target_id(self):
        if self.request.method == 'GET':
            return self.request.GET.get('target_id')
        elif self.request.method == 'POST':
            return self.request.POST.get('target_id')

    def get_target(self):
        return Target.objects.get(pk=self.get_target_id())

    def get_facility(self):
        return self.kwargs['facility']

    def get_facility_class(self):
        return get_service_class(self.get_facility())

    def get_form_class(self):
        return self.get_facility_class().form

    def get_form(self):
        form = super().get_form()
        form.helper.form_action = reverse(
            'tom_observations:create', kwargs=self.kwargs
        )
        return form

    def get_initial(self):
        initial = super().get_initial()
        if not self.get_target_id():
            raise Exception('Must provide target_id')
        initial['target_id'] = self.get_target_id()
        initial['facility'] = self.get_facility()
        return initial

    def form_valid(self, form):
        # Submit the observation
        facility = self.get_facility_class()
        target = self.get_target()
        observation_ids = facility().submit_observation(form.observation_payload)

        for observation_id in observation_ids:
            # Create Observation record
            ObservationRecord.objects.create(
                target=target,
                facility=facility.name,
                parameters=form.serialize_parameters(),
                observation_id=observation_id
            )
        return redirect(
            reverse('tom_targets:detail', kwargs={'pk': target.id})
        )


class ManualObservationCreateView(LoginRequiredMixin, FormView):
    template_name = 'tom_observations/observation_form_manual.html'
    form_class = ManualObservationForm

    def get_target_id(self):
        if self.request.method == 'GET':
            return self.request.GET.get('target_id')
        elif self.request.method == 'POST':
            return self.request.POST.get('target_id')

    def get_initial(self):
        initial = super().get_initial()
        if not self.get_target_id():
            raise Exception('Must provide target_id')
        initial['target_id'] = self.get_target_id()
        return initial

    def get_target(self):
        return Target.objects.get(pk=self.get_target_id())

    def form_valid(self, form):
        ObservationRecord.objects.create(
            target=self.get_target(),
            facility=form.cleaned_data['facility'],
            parameters={},
            observation_id=form.cleaned_data['observation_id']
        )
        return redirect(reverse(
            'tom_targets:detail', kwargs={'pk': self.get_target().id})
        )


class ObservationRecordDetailView(DetailView):
    model = ObservationRecord

    def get_queryset(self, *args, **kwargs):
        return ObservationRecord.objects.filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['form'] = AddProductToGroupForm()
        service_class = get_service_class(self.object.facility)
        context['data_products'] = service_class().all_data_products(self.object)
        newest_image = None
        for data_product in context['data_products']['saved']:
            newest_image = data_product if (not newest_image or data_product.modified > newest_image.modified) and \
                data_product.get_file_extension() == '.fits' else newest_image
        if newest_image:
            context['image'] = newest_image.get_image_data()
        return context
