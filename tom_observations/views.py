from io import StringIO
from urllib.parse import urlencode
import logging
from typing import List

from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import HTML, Layout, Submit
from django import forms
from django.core.exceptions import BadRequest
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
from django.views.generic import View, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView
from django.views.generic.list import ListView
from guardian.shortcuts import get_objects_for_user, assign_perm
from guardian.mixins import PermissionListMixin

from tom_common.hints import add_hint
from tom_common.mixins import Raise403PermissionRequiredMixin
from tom_dataproducts.forms import AddProductToGroupForm, DataProductUploadForm
from tom_dataproducts.models import is_fits_image_file
from tom_observations.cadence import CadenceForm, get_cadence_strategy
from tom_observations.facility import get_service_class, get_service_classes
from tom_observations.facility import BaseManualObservationFacility
from tom_observations.forms import AddExistingObservationForm
from tom_observations.models import ObservationRecord, ObservationGroup, ObservationTemplate, DynamicCadence
from tom_targets.models import Target

logger = logging.getLogger(__name__)


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
        # QueryDict is immutable, and we want to append the remaining parameters to the redirect URL
        query_params = request.GET.copy()
        update_status = query_params.pop('update_status', False)
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
            return redirect(f'{reverse("tom_observations:list")}?{urlencode(query_params)}')

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


# TODO: Ensure this template includes the ApplyObservationTemplate form at the top
class ObservationCreateView(LoginRequiredMixin, FormView):
    """
    View for creation/submission of an observation. Requires authentication.
    """
    template_name = 'tom_observations/observation_form.html'

    def get_template_names(self) -> List[str]:
        """Override the base class method to ask the Facility if it has
        specified a Facility-specific template to use. If so, put it at the
        front of the returned list of template_names.
        """
        template_names = super().get_template_names()

        # get the facility_class and its template_name, if defined
        facility_class = self.get_facility_class()
        try:
            if facility_class.template_name:
                # add to front of list b/c first template will be tried first
                template_names.insert(0, facility_class.template_name)
        except AttributeError:
            # some Facilities won't have a custom template_name defined and so
            # we will just use the one defined above.
            pass

        logger.debug(f'ObservationCreateView.get_template_name template_names: {template_names}')
        return template_names

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

    def get_cadence_strategy_form(self):
        cadence_strategy = self.request.GET.get('cadence_strategy')
        if not cadence_strategy:
            return CadenceForm
        return get_cadence_strategy(cadence_strategy).form

    def get_context_data(self, **kwargs):
        """
        Adds the available observation types for the observing facility to the context object.

        :returns: context dictionary
        :rtype: dict
        """
        context = super(ObservationCreateView, self).get_context_data(**kwargs)

        # Populate initial values for each form and add them to the context. If the page
        # reloaded due to form errors, only repopulate the form that was submitted.
        observation_type_choices = []
        initial = self.get_initial()
        for observation_type, observation_form_class in self.get_facility_class().observation_forms.items():
            form_data = {**initial, **{'observation_type': observation_type}}
            # Repopulate the appropriate form with form data if the original submission was invalid
            if observation_type == self.request.POST.get('observation_type'):
                form_data.update(**self.request.POST.dict())
            observation_form_class = type(f'Composite{observation_type}Form',
                                          (self.get_cadence_strategy_form(), observation_form_class), {})
            observation_type_choices.append((observation_type, observation_form_class(initial=form_data)))
        context['observation_type_choices'] = observation_type_choices

        # Ensure correct tab is active if submission is unsuccessful
        context['active'] = self.request.POST.get('observation_type')

        target = Target.objects.get(pk=self.get_target_id())
        context['target'] = target

        # allow the Facility class to add data to the context
        facility = self.get_facility_class()()
        facility.set_user(self.request.user)
        facility_context = facility.get_facility_context_data(target=target)
        context.update(facility_context)

        try:
            context['missing_configurations'] = ", ".join(facility.facility_settings.get_unconfigured_settings())
        except AttributeError:
            context['missing_configurations'] = ''

        return context

    def get_form_class(self):
        """
        Gets the observation form class for the facility and selected observation type in the query parameters.

        :returns: observation form
        :rtype: subclass of GenericObservationForm
        """
        observation_type = None
        if self.request.method == 'GET':
            observation_type = self.request.GET.get('observation_type')
        elif self.request.method == 'POST':
            observation_type = self.request.POST.get('observation_type')
        facility = self.get_facility_class()()
        facility.set_user(self.request.user)
        form_class = type(f'Composite{observation_type}Form',
                          (facility.get_form(observation_type), self.get_cadence_strategy_form()),
                          {})
        return form_class

    def get_form(self, form_class=None):
        """
        Gets an instance of the form appropriate for the request.

        :returns: observation form
        :rtype: subclass of GenericObservationForm
        """
        try:
            form = super().get_form()
        except Exception as ex:
            logger.error(f"Error loading {self.get_facility()} form: {repr(ex)}")
            raise BadRequest(f"Error loading {self.get_facility()} form: {repr(ex)}")

        # tom_observations/facility.BaseObservationForm.__init__ to see how
        # groups is added to common_layout
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
        initial.update(self.request.GET.dict())
        return initial

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            if 'validate' in request.POST:
                return self.form_validation_valid(form)
            else:
                return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_validation_valid(self, form):
        messages.info(self.request, form.get_validation_message())
        return self.render_to_response(self.get_context_data(request=self.request, form=form))

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
        facility = self.get_facility_class()()
        facility.set_user(self.request.user)
        target = self.get_target()
        observation_ids = facility.submit_observation(form.observation_payload())
        records = []

        for observation_id in observation_ids:
            # Create Observation record
            record = ObservationRecord.objects.create(
                target=target,
                user=self.request.user,
                facility=facility.name,
                parameters=form.serialize_parameters(),
                observation_id=observation_id
            )
            records.append(record)

        # TODO: redirect to observation list for multiple observations, observation detail otherwise

        if len(records) > 1 or form.cleaned_data.get('cadence_strategy'):
            observation_group = ObservationGroup.objects.create(name=form.cleaned_data['name'])
            observation_group.observation_records.add(*records)
            assign_perm('tom_observations.view_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.change_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.delete_observationgroup', self.request.user, observation_group)

            # TODO: Add a test case that includes a dynamic cadence submission
            if form.cleaned_data.get('cadence_strategy'):
                cadence_parameters = {}
                cadence_form = get_cadence_strategy(form.cleaned_data.get('cadence_strategy')).form
                for field in cadence_form().cadence_fields:
                    cadence_parameters[field] = form.cleaned_data.get(field)
                DynamicCadence.objects.create(
                    observation_group=observation_group,
                    cadence_strategy=form.cleaned_data.get('cadence_strategy'),
                    cadence_parameters=cadence_parameters,
                    active=True
                )

        if not settings.TARGET_PERMISSIONS_ONLY:
            groups = form.cleaned_data['groups']
            for record in records:
                assign_perm('tom_observations.view_observationrecord', groups, record)
                assign_perm('tom_observations.change_observationrecord', groups, record)
                assign_perm('tom_observations.delete_observationrecord', groups, record)

        return redirect(
            reverse('tom_targets:detail', kwargs={'pk': target.id}) + '?tab=observations'
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


class ObservationRecordCancelView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        obsr_id = self.kwargs.get('pk')
        obsr = ObservationRecord.objects.get(id=obsr_id)
        facility = get_service_class(obsr.facility)()
        facility.set_user(request.user)
        try:
            success = facility.cancel_observation(obsr.observation_id)
            if success:
                messages.success(self.request, f'Successfully cancelled observation {obsr}')
                facility.update_observation_status(obsr.observation_id)
            else:
                messages.error(self.request, 'Unable to cancel observation.')
        except forms.ValidationError as ve:
            messages.error(self.request, f'Unable to cancel observation: {ve}')

        return redirect(reverse('tom_observations:detail', kwargs={'pk': obsr.id}))


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

    def get_form(self, form_class=None):
        form = super().get_form()
        form.fields['facility'].widget = forms.HiddenInput()
        form.fields['observation_id'].widget = forms.HiddenInput()
        if self.request.method == 'GET':
            target_id = self.request.GET.get('target_id')
        elif self.request.method == 'POST':
            target_id = self.request.POST.get('target_id')
        cancel_url = reverse('home')
        if target_id:
            cancel_url = reverse('tom_targets:detail', kwargs={'pk': target_id}) + '?tab=observations'
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
        base_url = reverse('tom_targets:detail', kwargs={'pk': form.cleaned_data['target_id']})
        query_params = urlencode({'tab': 'observations'})
        return redirect(f'{base_url}?{query_params}')


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
        facility = get_service_class(self.object.facility)()
        facility.set_user(self.request.user)
        context['editable'] = isinstance(facility, BaseManualObservationFacility)
        context['data_products'] = facility.all_data_products(self.object)
        context['can_be_cancelled'] = self.object.status not in facility.get_terminal_observing_states()
        newest_image = None
        for data_product in context['data_products']['saved']:
            newest_image = data_product if (not newest_image or data_product.modified > newest_image.modified) and \
                is_fits_image_file(data_product.data.file) else newest_image
        if newest_image:
            context['image'] = newest_image.get_preview()
        data_product_upload_form = DataProductUploadForm(
            initial={
                'observation_record': self.get_object(),
                'referrer': reverse('tom_observations:detail', args=(self.get_object().id,))
            }
        )
        context['data_product_form'] = data_product_upload_form
        return context


class ObservationGroupCreateView(LoginRequiredMixin, CreateView):
    """
    View that handles the creation of ``ObservationGroup`` objects. Requires authentication.
    """
    model = ObservationGroup
    fields = ['name']
    success_url = reverse_lazy('tom_observations:group-list')

    def form_valid(self, form):
        """
        Runs after form validation. Saves the observation group and assigns the user's permissions to the group.

        :param form: Form data for observation group creation
        :type form: django.forms.ModelForm
        """
        obj = form.save(commit=False)
        obj.save()
        assign_perm('tom_observations.view_observationgroup', self.request.user, obj)
        assign_perm('tom_observations.change_observationgroup', self.request.user, obj)
        assign_perm('tom_observations.delete_observationgroup', self.request.user, obj)
        return super().form_valid(form)


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


class ObservationTemplateFilter(FilterSet):
    """
    Defines the available fields for filtering the list of ``ObservationTemplate`` objects.
    """
    facility = ChoiceFilter(
        choices=[(k, k) for k in get_service_classes().keys()]
    )
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = ObservationTemplate
        fields = ['name', 'facility']


class ObservationTemplateListView(FilterView):
    """
    Displays the observing strategies that exist in the TOM.
    """
    model = ObservationTemplate
    filterset_class = ObservationTemplateFilter
    template_name = 'tom_observations/observationtemplate_list.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['installed_facilities'] = get_service_classes()
        return context


class ObservationTemplateCreateView(FormView):
    """
    Displays the form for creating a new observation template. Uses the observation template form specified in the
    respective facility class.
    """
    template_name = 'tom_observations/observationtemplate_form.html'

    def get_facility_name(self):
        return self.kwargs['facility']

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        facility = get_service_class(self.get_facility_name())()
        # Check configuration of facility and pass names of missing settings to context as 'missing_configurations'.
        try:
            context['missing_configurations'] = ", ".join(facility.facility_settings.get_unconfigured_settings())
        except AttributeError:
            context['missing_configurations'] = ''
        return context

    def get_form_class(self):
        facility_name = self.get_facility_name()

        if not facility_name:
            raise ValueError('Must provide a facility name')

        # TODO: modify this to work with all LCO forms
        facility = get_service_class(facility_name)()
        facility.set_user(self.request.user)
        return facility.get_template_form(None)

    def get_form(self, form_class=None):
        form = super().get_form()
        form.helper.form_action = reverse('tom_observations:template-create',
                                          kwargs={'facility': self.get_facility_name()})
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial['facility'] = self.get_facility_name()
        initial.update(self.request.GET.dict())
        return initial

    def form_valid(self, form):
        form.save()
        return redirect(reverse('tom_observations:template-list'))


class ObservationTemplateUpdateView(LoginRequiredMixin, FormView):
    """
    View for updating an existing observation template.
    """
    template_name = 'tom_observations/observationtemplate_form.html'

    def get_object(self):
        return ObservationTemplate.objects.get(pk=self.kwargs['pk'])

    def get_form_class(self):
        self.object = self.get_object()
        facility = get_service_class(self.object.facility)()
        facility.set_user(self.request.user)
        return facility.get_template_form(None)

    def get_form(self, form_class=None):
        form = super().get_form()
        form.helper.form_action = reverse(
            'tom_observations:template-update', kwargs={'pk': self.object.id}
        )
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.object.parameters)
        initial['facility'] = self.object.facility
        return initial

    def form_valid(self, form):
        form.save(template_id=self.object.id)
        return redirect(reverse('tom_observations:template-list'))


class ObservationTemplateDeleteView(LoginRequiredMixin, DeleteView):
    """
    Deletes an observation template.
    """
    model = ObservationTemplate
    success_url = reverse_lazy('tom_observations:template-list')


class FacilityStatusView(TemplateView):
    template_name = 'tom_observations/facility_status.html'
