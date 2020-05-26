from io import StringIO
from urllib.parse import urlparse
import json

from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import HTML, Layout, Submit
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django_filters import (CharFilter, ChoiceFilter, DateTimeFromToRangeFilter, FilterSet, ModelMultipleChoiceFilter,
                            OrderingFilter)
from django_filters.views import FilterView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import DeleteView, FormView, UpdateView
from django.views.generic.list import ListView
from guardian.shortcuts import get_objects_for_user, assign_perm
from guardian.mixins import PermissionListMixin

from tom_common.hints import add_hint
from tom_common.mixins import Raise403PermissionRequiredMixin
from tom_dataproducts.forms import AddProductToGroupForm, DataProductUploadForm
from tom_observations.facility import get_service_class, get_service_classes, BaseManualObservationFacility
from tom_observations.forms import AddExistingObservationForm
from tom_observations.models import ObservationRecord, ObservationGroup, ObservingStrategy
from tom_targets.models import Target


class ObservationFilter(FilterSet):
    """
    Defines the available fields for filtering the list of ``ObservationRecord`` objects.
    """
    ordering = OrderingFilter(
        fields=['scheduled_start', 'scheduled_end', 'status', 'created', 'modified']
    )
    scheduled_start = DateTimeFromToRangeFilter()
    scheduled_end = DateTimeFromToRangeFilter
    observationgroup = ModelMultipleChoiceFilter(
        label='Observation Groups', queryset=ObservationGroup.objects.all()
    )

    class Meta:
        model = ObservationRecord
        fields = ['ordering', 'observation_id', 'target_id', 'observationgroup', 'facility', 'status']


class ObservationListView(FilterView):
    """
    View that displays all ``ObservationRecord`` objects.
    """
    filterset_class = ObservationFilter
    template_name = 'tom_observations/observation_list.html'
    paginate_by = 25
    model = ObservationRecord
    strict = False

    def get_queryset(self, *args, **kwargs):
        """
        Gets the set of ``ObservationRecord`` objects associated with the targets that the user is authorized to view.

        :returns: set of ObservationRecords
        :rtype: QuerySet
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            return ObservationRecord.objects.filter(
                target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_observations.view_observationrecord')

    def get(self, request, *args, **kwargs):
        """
        Handles the GET requests to this view. If update_status is passed in the query parameters, calls the
        updatestatus management command to query for new statuses for ``ObservationRecord`` objects.

        :param request: request object for this GET request
        :type request: HTTPRequest
        """
        update_status = request.GET.get('update_status', False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            out = StringIO()
            call_command('updatestatus', stdout=out)
            messages.info(request, out.getvalue())
            add_hint(request, mark_safe(
                              'Did you know updating observation statuses can be automated? Learn how in '
                              '<a href=https://tom-toolkit.readthedocs.io/en/stable/customization/automation.html>'
                              'the docs.</a>'))
            return redirect(reverse('tom_observations:list'))

        selected = request.GET.getlist('selected')
        observationgroups = request.GET.getlist('observationgroup')
        action = request.GET.get('action')
        if selected and observationgroups and action:
            observation_records = ObservationRecord.objects.filter(id__in=selected)
            groups = ObservationGroup.objects.filter(id__in=observationgroups)
            for group in groups:
                if action == 'add':
                    group.observation_records.add(*observation_records)
                if action == 'remove':
                    group.observation_records.remove(*observation_records)
                group.save()
            return redirect(reverse('tom_observations:list'))
        return super().get(request, *args, **kwargs)


class ObservationCreateView(LoginRequiredMixin, FormView):
    """
    View for creation/submission of an observation. Requries authentication.
    """
    template_name = 'tom_observations/observation_form.html'

    def get_target_id(self):
        """
        Parses the target id for the given observation from the query parameters.

        :returns: id of the target for observing
        :rtype: int
        """
        if self.request.method == 'GET':
            return self.request.GET.get('target_id')
        elif self.request.method == 'POST':
            return self.request.POST.get('target_id')

    def get_target(self):
        """
        Gets the target for observing from the database

        :returns: target for observing
        :rtype: Target
        """
        return Target.objects.get(pk=self.get_target_id())

    def get_facility(self):
        """
        Gets the facility from which the target is being observed from the query parameters

        :returns: facility name
        :rtype: str
        """
        return self.kwargs['facility']

    def get_facility_class(self):
        """
        Gets the facility interface class

        :returns: facility class name
        :rtype: str
        """
        return get_service_class(self.get_facility())

    def get_observation_type(self):
        """
        Gets the observation type from the query parameters of the request.

        :returns: observation type
        :rtype: str
        """
        if self.request.method == 'GET':
            # TODO: This appears to not work as intended.
            return self.request.GET.get('observation_type', self.get_facility_class().observation_types[0])
        elif self.request.method == 'POST':
            return self.request.POST.get('observation_type')

    def get_context_data(self, **kwargs):
        """
        Adds the available observation types for the observing facility to the context object.

        :returns: context dictionary
        :rtype: dict
        """
        context = super(ObservationCreateView, self).get_context_data(**kwargs)
        context['type_choices'] = self.get_facility_class().observation_types
        target = Target.objects.get(pk=self.get_target_id())
        context['target'] = target
        return context

    def get_form_class(self):
        """
        Gets the observation form class for the facility and selected observation type in the query parameters.

        :returns: observation form
        :rtype: subclass of GenericObservationForm
        """
        observation_type = None
        if self.request.GET:
            observation_type = self.request.GET.get('observation_type')
        elif self.request.POST:
            observation_type = self.request.POST.get('observation_type')
        return self.get_facility_class()().get_form(observation_type)

    def get_form(self):
        """
        Gets an instance of the form appropriate for the request.

        :returns: observation form
        :rtype: subclass of GenericObservationForm
        """
        form = super().get_form()
        if not settings.TARGET_PERMISSIONS_ONLY:
            form.fields['groups'].queryset = self.request.user.groups.all()
        form.helper.form_action = reverse(
            'tom_observations:create', kwargs=self.kwargs
        )
        return form

    def get_initial(self):
        """
        Populates the observation form with initial data including the id of the target to be observed, the facility at
        which the observation will take place, and the observation type desired.

        :returns: initial form data
        :rtype: dict
        """
        initial = super().get_initial()
        if not self.get_target_id():
            raise Exception('Must provide target_id')
        initial['target_id'] = self.get_target_id()
        initial['facility'] = self.get_facility()
        initial['observation_type'] = self.get_observation_type()
        initial.update(self.request.GET.dict())
        return initial

    def form_valid(self, form):
        """
        Runs after form validation. Submits the observation to the desired facility and creates an associated
        ``ObservationRecord``, then redirects to the detail page of the target to be observed.

        If the facility returns more than one record, a group is created and all observation
        records from the request are added to it.

        :param form: form containing observating request parameters
        :type form: subclass of GenericObservationForm
        """
        # Submit the observation
        facility = self.get_facility_class()
        target = self.get_target()
        observation_ids = facility().submit_observation(form.observation_payload())
        records = []

        for observation_id in observation_ids:
            # Create Observation record
            record = ObservationRecord.objects.create(
                target=target,
                facility=facility.name,
                parameters=form.serialize_parameters(),
                observation_id=observation_id
            )
            records.append(record)

        # TODO: redirect to observation list for multiple observations, observation detail otherwise

        if len(records) > 1 or form.cleaned_data.get('cadence_strategy'):
            group_name = form.cleaned_data['name']
            observation_group = ObservationGroup.objects.create(
                name=group_name, cadence_strategy=form.cleaned_data.get('cadence_strategy'),
                cadence_parameters=json.dumps({'cadence_frequency': form.cleaned_data.get('cadence_frequency')})
            )
            observation_group.observation_records.add(*records)
            assign_perm('tom_observations.view_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.change_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.delete_observationgroup', self.request.user, observation_group)

        if not settings.TARGET_PERMISSIONS_ONLY:
            groups = form.cleaned_data['groups']
            for record in records:
                assign_perm('tom_observations.view_observationrecord', groups, record)
                assign_perm('tom_observations.change_observationrecord', groups, record)
                assign_perm('tom_observations.delete_observationrecord', groups, record)

        return redirect(
            reverse('tom_targets:detail', kwargs={'pk': target.id})
        )


class ObservationRecordUpdateView(LoginRequiredMixin, UpdateView):
    """
    This view allows for the updating of the observation id, which will eventually be expanded to more fields.
    """
    model = ObservationRecord
    fields = ['observation_id']
    template_name = 'tom_observations/observationupdate_form.html'

    def get_success_url(self):
        return reverse('tom_observations:detail', kwargs={'pk': self.get_object().id})


class ObservationGroupCancelView(LoginRequiredMixin, View):

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['next'] = self.request.META.get('HTTP_REFERER', '/')
        return context

    def get(self, request, *args, **kwargs):
        obsr_id = self.kwargs.get('pk')
        obsr = ObservationRecord.objects.get(id=obsr_id)
        facility = get_service_class(obsr.facility)()
        errors = facility.cancel_observation(obsr.observation_id)
        if errors:
            messages.error(
                self.request,
                f'Unable to cancel observation: {errors}'
            )

        referer = self.request.GET('next', None)
        referer = urlparse(referer).path if referer else '/'
        return redirect(referer)


class AddExistingObservationView(LoginRequiredMixin, FormView):
    """
    View for associating a pre-existing observation with a target. Requires authentication.

    The GET view returns a confirmation page for adding duplicate ObservationRecords. Two duplicates are any two
    ObservationRecords with the same target_id, facility, and observation_id.

    The POST view validates the form and redirects to the confirmation page if the confirm flag isn't set.

    This view is intended to be navigated to via the existing_observation_button templatetag, as the
    AddExistingObservationForm has a hidden confirmation checkbox selected by default.
    """
    template_name = 'tom_observations/existing_observation_confirm.html'
    form_class = AddExistingObservationForm

    def get_form(self):
        form = super().get_form()
        form.fields['facility'].widget = forms.HiddenInput()
        form.fields['observation_id'].widget = forms.HiddenInput()
        if self.request.method == 'GET':
            target_id = self.request.GET.get('target_id')
        elif self.request.method == 'POST':
            target_id = self.request.POST.get('target_id')
        cancel_url = reverse('home')
        if target_id:
            cancel_url = reverse('tom_targets:detail', kwargs={'pk': target_id})
        form.helper.layout = Layout(
            HTML('''<p>An observation record already exists in your TOM for this combination of observation ID,
                 facility, and target. Are you sure you want to create this record?</p>'''),
            'target_id',
            'facility',
            'observation_id',
            'confirm',
            FormActions(
                Submit('confirm', 'Confirm'),
                HTML(f'<a class="btn btn-outline-primary" href={cancel_url}>Cancel</a>')
            )
        )
        return form

    def get_initial(self):
        """
        Populates the ``ManualObservationForm`` hidden field for target id with the id from the specified target.

        :returns: initial form data
        :rtype: dict
        """
        if self.request.method == 'GET':
            params = self.request.GET.dict()
            params['confirm'] = True
            return params

    def form_valid(self, form):
        """
        Runs after form validation. Creates a new ``ObservationRecord`` associated with the specified target and
        facility.
        """
        records = ObservationRecord.objects.filter(target_id=form.cleaned_data['target_id'],
                                                   facility=form.cleaned_data['facility'],
                                                   observation_id=form.cleaned_data['observation_id'])

        if records and not form.cleaned_data.get('confirm'):
            return redirect(reverse('tom_observations:add-existing') + '?' + self.request.POST.urlencode())
        else:
            ObservationRecord.objects.create(
                target_id=form.cleaned_data['target_id'],
                facility=form.cleaned_data['facility'],
                parameters={},
                observation_id=form.cleaned_data['observation_id']
            )
            observation_id = form.cleaned_data['observation_id']
            messages.success(self.request, f'Successfully associated observation record {observation_id}')
        return redirect(reverse(
            'tom_targets:detail', kwargs={'pk': form.cleaned_data['target_id']})
        )


class ObservationRecordDetailView(DetailView):
    """
    View for displaying the details of an ``ObservationRecord`` object.
    """
    model = ObservationRecord

    def get_queryset(self, *args, **kwargs):
        """
        Gets the set of ``ObservationRecord`` objects associated with targets that the current user is authorized to
        view.

        :returns: set of ObservationRecords
        :rtype: QuerySet
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            return ObservationRecord.objects.filter(
                target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_observations.view_observationrecord')

    def get_context_data(self, *args, **kwargs):
        """
        Adds a number of items to the context object for this view, including the form for adding resulting
        ``DataProduct`` objects to a ``DataProductGroup``, the ``DataProduct`` objects associated with the
        ``ObservationRecord``, and the most recent image from this ``ObservationRecord``. It also populates the
        ``DataProductUploadForm`` hidden fields with initial data.

        :returns: context dictionary
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        context['form'] = AddProductToGroupForm()
        service_class = get_service_class(self.object.facility)
        context['editable'] = isinstance(service_class(), BaseManualObservationFacility)
        context['data_products'] = service_class().all_data_products(self.object)
        context['can_be_cancelled'] = self.object.status not in service_class().get_terminal_observing_states()
        newest_image = None
        for data_product in context['data_products']['saved']:
            newest_image = data_product if (not newest_image or data_product.modified > newest_image.modified) and \
                data_product.get_file_extension() == '.fits' else newest_image
        if newest_image:
            context['image'] = newest_image.get_image_data()
        data_product_upload_form = DataProductUploadForm(
            initial={
                'observation_record': self.get_object(),
                'referrer': reverse('tom_observations:detail', args=(self.get_object().id,))
            }
        )
        context['data_product_form'] = data_product_upload_form
        return context


class ObservationGroupListView(PermissionListMixin, ListView):
    """
    View that handles the display of ``ObservationGroup``.
    Requires authorization.
    """
    permission_required = 'tom_observations.view_observationgroup'
    model = ObservationGroup
    paginate_by = 25


class ObservationGroupDeleteView(Raise403PermissionRequiredMixin, DeleteView):
    """
    View that handles the deletion of ``ObservationGroup`` objects. Requires authorization.
    """
    permission_required = 'tom_observations.delete_observationgroup'
    model = ObservationGroup
    success_url = reverse_lazy('tom_observations:group-list')


class ObservingStrategyFilter(FilterSet):
    """
    Defines the available fields for filtering the list of ``ObservingStrategy`` objects.
    """
    facility = ChoiceFilter(
        choices=[(k, k) for k in get_service_classes().keys()]
    )
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = ObservingStrategy
        fields = ['name', 'facility']


class ObservingStrategyListView(FilterView):
    """
    Displays the observing strategies that exist in the TOM.
    """
    model = ObservingStrategy
    filterset_class = ObservingStrategyFilter
    template_name = 'tom_observations/observingstrategy_list.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['installed_facilities'] = get_service_classes()
        return context


class ObservingStrategyCreateView(FormView):
    """
    Displays the form for creating a new observing strategy. Uses the observing strategy form specified in the
    respective facility class.
    """
    template_name = 'tom_observations/observingstrategy_form.html'

    def get_facility_name(self):
        return self.kwargs['facility']

    def get_form_class(self):
        facility_name = self.get_facility_name()

        if not facility_name:
            raise ValueError('Must provide a facility name')

        # TODO: modify this to work with both LCO forms
        return get_service_class(facility_name)().get_strategy_form(None)

    def get_form(self, form_class=None):
        form = super().get_form()
        form.helper.form_action = reverse('tom_observations:strategy-create',
                                          kwargs={'facility': self.get_facility_name()})
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial['facility'] = self.get_facility_name()
        initial.update(self.request.GET.dict())
        return initial

    def form_valid(self, form):
        form.save()
        return redirect(reverse('tom_observations:strategy-list'))


class ObservingStrategyUpdateView(LoginRequiredMixin, FormView):
    """
    View for updating an existing observing strategy.
    """
    template_name = 'tom_observations/observingstrategy_form.html'

    def get_object(self):
        return ObservingStrategy.objects.get(pk=self.kwargs['pk'])

    def get_form_class(self):
        self.object = self.get_object()
        return get_service_class(self.object.facility)().get_strategy_form(None)

    def get_form(self):
        form = super().get_form()
        form.helper.form_action = reverse(
            'tom_observations:strategy-update', kwargs={'pk': self.object.id}
        )
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.object.parameters_as_dict)
        initial['facility'] = self.object.facility
        return initial

    def form_valid(self, form):
        form.save(strategy_id=self.object.id)
        return redirect(reverse('tom_observations:strategy-list'))


class ObservingStrategyDeleteView(LoginRequiredMixin, DeleteView):
    """
    Deletes an observing strategy.
    """
    model = ObservingStrategy
    success_url = reverse_lazy('tom_observations:strategy-list')
