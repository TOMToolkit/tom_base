from io import StringIO

from django.views.generic.edit import FormView, DeleteView, CreateView
from django.views.generic.list import ListView
from django.views.generic import View
from django_filters.views import FilterView
from django.views.generic.detail import DetailView
from tom_observations.facility import get_service_class
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from django.core.management import call_command
from django.contrib import messages

from .models import ObservationRecord, DataProduct, DataProductGroup
from .forms import ManualObservationForm, AddProductToGroupForm
from tom_targets.models import Target


class ObservationListView(FilterView):
    template_name = 'tom_observations/observation_list.html'
    paginate_by = 100
    model = ObservationRecord
    filterset_fields = ['observation_id', 'target_id', 'facility', 'status']

    def get(self, request, *args, **kwargs):
        update_status = request.GET.get('update_status', False)
        if update_status:
            out = StringIO()
            call_command('updatestatus', stdout=out)
            messages.info(request, out.getvalue())
            return redirect(reverse('tom_observations:list'))
        return super().get(request, *args, **kwargs)


class ObservationCreateView(FormView):
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
        form.helper.form_action = reverse('tom_observations:create', kwargs=self.kwargs)
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
        observation_ids = facility.submit_observation(form.observation_payload)

        for observation_id in observation_ids:
            # Create Observation record
            ObservationRecord.objects.create(
                target=target,
                facility=facility.name,
                parameters=form.serialize_parameters(),
                observation_id=observation_id
            )
        return redirect(reverse('tom_targets:detail', kwargs={'pk': target.id}))


class ManualObservationCreateView(FormView):
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
        return redirect(reverse('tom_targets:detail', kwargs={'pk': self.get_target().id}))


class ObservationRecordDetailView(DetailView):
    model = ObservationRecord

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['form'] = AddProductToGroupForm()
        context['data_products'] = get_service_class(self.object.facility).data_products(self.object)
        return context


class DataProductSaveView(View):
    def post(self, request, *args, **kwargs):
        service_class = get_service_class(request.POST['facility'])
        observation_record = ObservationRecord.objects.get(pk=kwargs['pk'])
        product_id = request.POST['product_id']
        if product_id == 'ALL':
            products = service_class.save_data_products(observation_record)
        else:
            products = service_class.save_data_products(observation_record, product_id)
        messages.success(request, 'Successfully saved: {0}'.format('\n'.join([str(p) for p in products])))
        return redirect(reverse('tom_observations:detail', kwargs={'pk': observation_record.id}))


class DataProductDeleteView(DeleteView):
    model = DataProduct

    def get_success_url(self):
        return reverse('tom_observations:detail', kwargs={'pk': self.object.observation_record.id})

    def delete(self, request, *args, **kwargs):
        self.get_object().data.delete()
        return super().delete(request, *args, **kwargs)


class DataProductListView(FilterView):
    model = DataProduct
    template_name = 'tom_observations/dataproduct_list.html'
    paginate_by = 25
    filterset_fields = ['target__identifier', 'observation_record__facility']


class DataProductGroupDetailView(DetailView):
    model = DataProductGroup

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        for product in request.POST.getlist('products'):
            group.dataproduct_set.remove(DataProduct.objects.get(pk=product))
        group.save()
        return redirect(reverse('tom_observations:data-group-detail', kwargs={'pk': group.id}))


class DataProductGroupListView(ListView):
    model = DataProductGroup


class DataProductGroupCreateView(CreateView):
    model = DataProductGroup
    success_url = reverse_lazy('tom_observations:data-group-list')
    fields = ['name']


class DataProductGroupDeleteView(DeleteView):
    success_url = reverse_lazy('tom_observations:data-group-list')
    model = DataProductGroup


class GroupDataView(FormView):
    form_class = AddProductToGroupForm
    template_name = 'tom_observations/add_product_to_group.html'

    def form_valid(self, form):
        group = form.cleaned_data['group']
        group.dataproduct_set.add(*form.cleaned_data['products'])
        group.save()
        return redirect(reverse('tom_observations:data-group-detail', kwargs={'pk': group.id}))
