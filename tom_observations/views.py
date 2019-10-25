from io import StringIO
import django_filters

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from django_filters.views import FilterView
from guardian.shortcuts import get_objects_for_user

from .models import ObservationRecord
from .forms import ManualObservationForm
from tom_common.hints import add_hint
from tom_dataproducts.forms import AddProductToGroupForm, DataProductUploadForm
from tom_targets.models import Target
from tom_observations.facility import get_service_class


class ObservationFilter(django_filters.FilterSet):
    """
    Defines the available fields for filtering the list of ``ObservationRecord`` objects.
    """
    ordering = django_filters.OrderingFilter(
        fields=['scheduled_start', 'scheduled_end', 'status', 'created', 'modified']
    )
    scheduled_start = django_filters.DateTimeFromToRangeFilter()
    scheduled_end = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = ObservationRecord
        fields = ['ordering', 'observation_id', 'target_id', 'facility', 'status']


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
        return ObservationRecord.objects.filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        )

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
        return context

    def get_form_class(self):
        """
        Gets the observation form class for the facility and selected observation type in the query parameters.

        :returns: observation form
        :rtype: subclass of GenericObservationForm
        """
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
        return initial

    def form_valid(self, form):
        """
        Runs after form validation. Submits the observation to the desired facility and creates an associated
        ``ObservationRecord``, then redirects to the detail page of the target to be observed.

        :param form: form containing observating request parameters
        :type form: subclass of GenericObservationForm
        """
        # Submit the observation
        facility = self.get_facility_class()
        target = self.get_target()
        observation_ids = facility().submit_observation(form.observation_payload())

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
    """
    View for associating a pre-existing observation with a target. Requires authentication.

    This view is not currently exposed in the out-of-the-box TOM Toolkit.
    """
    template_name = 'tom_observations/observation_form_manual.html'
    form_class = ManualObservationForm

    def get_target_id(self):
        """
        Gets the id of the target of the observation from the query parameters.

        :returns: target id
        :rtype: int
        """
        if self.request.method == 'GET':
            return self.request.GET.get('target_id')
        elif self.request.method == 'POST':
            return self.request.POST.get('target_id')

    def get_initial(self):
        """
        Populates the ``ManualObservationForm`` hidden field for target id with the id from the specified target.

        :returns: initial form data
        :rtype: dict
        """
        initial = super().get_initial()
        if not self.get_target_id():
            raise Exception('Must provide target_id')
        initial['target_id'] = self.get_target_id()
        return initial

    def get_target(self):
        """
        Gets the ``Target`` associated with the specified target_id from the database.

        :returns: target instance to be associated with an observation
        :rtype: Target
        """
        return Target.objects.get(pk=self.get_target_id())

    def form_valid(self, form):
        """
        Runs after form validation. Creates a new ``ObservationRecord`` associated with the specified target and
        facility.
        """
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
        return ObservationRecord.objects.filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        )

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
        context['data_products'] = service_class().all_data_products(self.object)
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
