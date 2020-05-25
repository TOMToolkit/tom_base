import logging

from datetime import datetime
from io import StringIO
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import transaction
from django.http import QueryDict, StreamingHttpResponse
from django.forms import HiddenInput
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic import TemplateView, View
from django_filters.views import FilterView

from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user, get_groups_with_perms, assign_perm

from tom_common.hints import add_hint
from tom_common.hooks import run_hook
from tom_common.mixins import Raise403PermissionRequiredMixin
from tom_observations.observing_strategy import RunStrategyForm
from tom_observations.models import ObservingStrategy
from tom_targets.models import Target, TargetList
from tom_targets.forms import (
    SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset, TargetNamesFormset
)
from tom_targets.utils import import_targets, export_targets
from tom_targets.filters import TargetFilter
from tom_targets.groups import add_all_to_grouping, add_selected_to_grouping
from tom_targets.groups import remove_all_from_grouping, remove_selected_from_grouping

logger = logging.getLogger(__name__)


class TargetListView(PermissionListMixin, FilterView):
    """
    View for listing targets in the TOM. Only shows targets that the user is authorized to view. Requires authorization.
    """
    template_name = 'tom_targets/target_list.html'
    paginate_by = 25
    strict = False
    model = Target
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target'

    def get_context_data(self, *args, **kwargs):
        """
        Adds the number of targets visible, the available ``TargetList`` objects if the user is authenticated, and
        the query string to the context object.

        :returns: context dictionary
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        context['target_count'] = context['paginator'].count
        # hide target grouping list if user not logged in
        context['groupings'] = (TargetList.objects.all()
                                if self.request.user.is_authenticated
                                else TargetList.objects.none())
        context['query_string'] = self.request.META['QUERY_STRING']
        return context


class TargetCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating a Target. Requires authentication.
    """

    model = Target
    fields = '__all__'

    def get_default_target_type(self):
        """
        Returns the user-configured target type specified in ``settings.py``, if it exists, otherwise returns sidereal

        :returns: User-configured target type or global default
        :rtype: str
        """
        try:
            return settings.TARGET_TYPE
        except AttributeError:
            return Target.SIDEREAL

    def get_target_type(self):
        """
        Gets the type of the target to be created from the query parameters. If none exists, use the default target
        type specified in ``settings.py``.

        :returns: target type
        :rtype: str
        """
        obj = self.request.GET or self.request.POST
        target_type = obj.get('type')
        # If None or some invalid value, use default target type
        if target_type not in (Target.SIDEREAL, Target.NON_SIDEREAL):
            target_type = self.get_default_target_type()
        return target_type

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.

        :returns: Dictionary with the following keys:

                  `type`: ``str``: Type of the target to be created

                  `groups`: ``QuerySet<Group>`` Groups available to the current user

        :rtype: dict
        """
        return {
            'type': self.get_target_type(),
            'groups': self.request.user.groups.all(),
            **dict(self.request.GET.items())
        }

    def get_context_data(self, **kwargs):
        """
        Inserts certain form data into the context dict.

        :returns: Dictionary with the following keys:

                  `type_choices`: ``tuple``: Tuple of 2-tuples of strings containing available target types in the TOM

                  `extra_form`: ``FormSet``: Django formset with fields for arbitrary key/value pairs
        :rtype: dict
        """
        context = super(TargetCreateView, self).get_context_data(**kwargs)
        context['type_choices'] = Target.TARGET_TYPES
        context['names_form'] = TargetNamesFormset(initial=[{'name': new_name}
                                                            for new_name
                                                            in self.request.GET.get('names', '').split(',')])
        context['extra_form'] = TargetExtraFormset()
        return context

    def get_form_class(self):
        """
        Return the form class to use in this view.

        :returns: form class for target creation
        :rtype: subclass of TargetCreateForm
        """
        target_type = self.get_target_type()
        self.initial['type'] = target_type
        if target_type == Target.SIDEREAL:
            return SiderealTargetCreateForm
        else:
            return NonSiderealTargetCreateForm

    def form_valid(self, form):
        """
        Runs after form validation. Creates the ``Target``, and creates any ``TargetName`` or ``TargetExtra`` objects,
        then runs the ``target_post_save`` hook and redirects to the success URL.

        :param form: Form data for target creation
        :type form: subclass of TargetCreateForm
        """
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST)
        names = TargetNamesFormset(self.request.POST)
        if extra.is_valid() and names.is_valid():
            extra.instance = self.object
            extra.save()
            names.instance = self.object
            names.save()
        else:
            form.add_error(None, extra.errors)
            form.add_error(None, extra.non_form_errors())
            form.add_error(None, names.errors)
            form.add_error(None, names.non_form_errors())
            return super().form_invalid(form)
        logger.info('Target post save hook: %s created: %s', self.object, True)
        run_hook('target_post_save', target=self.object, created=True)
        return redirect(self.get_success_url())

    def get_form(self, *args, **kwargs):
        """
        Gets an instance of the ``TargetCreateForm`` and populates it with the groups available to the current user.

        :returns: instance of creation form
        :rtype: subclass of TargetCreateForm
        """
        form = super().get_form(*args, **kwargs)
        if self.request.user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = self.request.user.groups.all()
        return form


class TargetUpdateView(Raise403PermissionRequiredMixin, UpdateView):
    """
    View that handles updating a target. Requires authorization.
    """
    permission_required = 'tom_targets.change_target'
    model = Target
    fields = '__all__'

    def get_context_data(self, **kwargs):
        """
        Adds formset for ``TargetName`` and ``TargetExtra`` to the context.

        :returns: context object
        :rtype: dict
        """
        extra_field_names = [extra['name'] for extra in settings.EXTRA_FIELDS]
        context = super().get_context_data(**kwargs)
        context['names_form'] = TargetNamesFormset(instance=self.object)
        context['extra_form'] = TargetExtraFormset(
            instance=self.object,
            queryset=self.object.targetextra_set.exclude(key__in=extra_field_names)
        )
        return context

    @transaction.atomic
    def form_valid(self, form):
        """
        Runs after form validation. Validates and saves the ``TargetExtra`` and ``TargetName`` formsets, then calls the
        superclass implementation of ``form_valid``, which saves the ``Target``. If any forms are invalid, rolls back
        the changes.

        Saving is done in this order to ensure that new names/extras are available in the ``target_post_save`` hook.

        :param form: Form data for target update
        :type form: subclass of TargetCreateForm
        """
        extra = TargetExtraFormset(self.request.POST, instance=self.object)
        names = TargetNamesFormset(self.request.POST, instance=self.object)
        if extra.is_valid() and names.is_valid():
            extra.save()
            names.save()
        else:
            form.add_error(None, extra.errors)
            form.add_error(None, extra.non_form_errors())
            form.add_error(None, names.errors)
            form.add_error(None, names.non_form_errors())
            return super().form_invalid(form)
        super().form_valid(form)
        return redirect(self.get_success_url())

    def get_queryset(self, *args, **kwargs):
        """
        Returns the queryset that will be used to look up the Target by limiting the result to targets that the user is
        authorized to modify.

        :returns: Set of targets
        :rtype: QuerySet
        """
        return get_objects_for_user(self.request.user, 'tom_targets.change_target')

    def get_form_class(self):
        """
        Return the form class to use in this view.

        :returns: form class for target update
        :rtype: subclass of TargetCreateForm
        """
        if self.object.type == Target.SIDEREAL:
            return SiderealTargetCreateForm
        elif self.object.type == Target.NON_SIDEREAL:
            return NonSiderealTargetCreateForm

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view. For the ``TargetUpdateView``, adds the groups that the
        target is a member of.

        :returns:
        :rtype: dict
        """
        initial = super().get_initial()
        initial['groups'] = get_groups_with_perms(self.get_object())
        return initial

    def get_form(self, *args, **kwargs):
        """
        Gets an instance of the ``TargetCreateForm`` and populates it with the groups available to the current user.

        :returns: instance of creation form
        :rtype: subclass of TargetCreateForm
        """
        form = super().get_form(*args, **kwargs)
        if self.request.user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = self.request.user.groups.all()
        return form


class TargetDeleteView(Raise403PermissionRequiredMixin, DeleteView):
    """
    View for deleting a target. Requires authorization.
    """
    permission_required = 'tom_targets.delete_target'
    success_url = reverse_lazy('targets:list')
    model = Target


class TargetDetailView(Raise403PermissionRequiredMixin, DetailView):
    """
    View that handles the display of the target details. Requires authorization.
    """
    permission_required = 'tom_targets.view_target'
    model = Target

    def get_context_data(self, *args, **kwargs):
        """
        Adds the ``DataProductUploadForm`` to the context and prepopulates the hidden fields.

        :returns: context object
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        observing_strategy_form = RunStrategyForm(initial={'target': self.get_object()})
        if any(self.request.GET.get(x) for x in ['observing_strategy', 'cadence_strategy', 'cadence_frequency']):
            initial = {'target': self.object}
            initial.update(self.request.GET)
            observing_strategy_form = RunStrategyForm(
                initial=initial
            )
        observing_strategy_form.fields['target'].widget = HiddenInput()
        context['observing_strategy_form'] = observing_strategy_form
        return context

    def get(self, request, *args, **kwargs):
        """
        Handles the GET requests to this view. If update_status is passed into the query parameters, calls the
        updatestatus management command to query for new statuses for ``ObservationRecord`` objects associated with this
        target.

        :param request: the request object passed to this view
        :type request: HTTPRequest
        """
        update_status = request.GET.get('update_status', False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            target_id = kwargs.get('pk', None)
            out = StringIO()
            call_command('updatestatus', target_id=target_id, stdout=out)
            messages.info(request, out.getvalue())
            add_hint(request, mark_safe(
                              'Did you know updating observation statuses can be automated? Learn how in'
                              '<a href=https://tom-toolkit.readthedocs.io/en/stable/customization/automation.html>'
                              ' the docs.</a>'))
            return redirect(reverse('tom_targets:detail', args=(target_id,)))

        run_strategy_form = RunStrategyForm(request.GET)
        if run_strategy_form.is_valid():
            obs_strat = ObservingStrategy.objects.get(pk=run_strategy_form.cleaned_data['observing_strategy'].id)
            params = urlencode(obs_strat.parameters_as_dict)
            return redirect(
                reverse('tom_observations:create',
                        args=(obs_strat.facility,)) + f'?target_id={self.get_object().id}&' + params)

        return super().get(request, *args, **kwargs)


class TargetImportView(LoginRequiredMixin, TemplateView):
    """
    View that handles the import of targets from a CSV. Requires authentication.
    """
    template_name = 'tom_targets/target_import.html'

    def post(self, request):
        """
        Handles the POST requests to this view. Creates a StringIO object and passes it to ``import_targets``.

        :param request: the request object passed to this view
        :type request: HTTPRequest
        """
        csv_file = request.FILES['target_csv']
        csv_stream = StringIO(csv_file.read().decode('utf-8'), newline=None)
        result = import_targets(csv_stream)
        messages.success(
            request,
            'Targets created: {}'.format(len(result['targets']))
        )
        for error in result['errors']:
            messages.warning(request, error)
        return redirect(reverse('tom_targets:list'))


class TargetExportView(TargetListView):
    """
    View that handles the export of targets to a CSV. Only exports selected targets.
    """
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response containing the exported CSV of selected targets.

        :param context: Context object for this view
        :type context: dict

        :returns: response class with CSV
        :rtype: StreamingHttpResponse
        """
        qs = context['filter'].qs.values()
        file_buffer = export_targets(qs)
        file_buffer.seek(0)  # goto the beginning of the buffer
        response = StreamingHttpResponse(file_buffer, content_type="text/csv")
        filename = "targets-{}.csv".format(slugify(datetime.utcnow()))
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        return response


class TargetAddRemoveGroupingView(LoginRequiredMixin, View):
    """
    View that handles addition and removal of targets to target groups. Requires authentication.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles the POST requests to this view. Routes the information from the request and query parameters to the
        appropriate utility method in ``groups.py``.

        :param request: the request object passed to this view
        :type request: HTTPRequest
        """
        query_string = request.POST.get('query_string', '')
        grouping_id = request.POST.get('grouping')
        filter_data = QueryDict(query_string)
        try:
            grouping_object = TargetList.objects.get(pk=grouping_id)
        except Exception as e:
            messages.error(request, 'Cannot find the target group with id={}; {}'.format(grouping_id, e))
            return redirect(reverse('tom_targets:list') + '?' + query_string)
        if not request.user.has_perm('tom_targets.view_targetlist', grouping_object):
            messages.error(request, 'Permission denied.')
            return redirect(reverse('tom_targets:list') + '?' + query_string)

        if 'add' in request.POST:
            if request.POST.get('isSelectAll') == 'True':
                add_all_to_grouping(filter_data, grouping_object, request)
            else:
                targets_ids = request.POST.getlist('selected-target')
                add_selected_to_grouping(targets_ids, grouping_object, request)
        if 'remove' in request.POST:
            if request.POST.get('isSelectAll') == 'True':
                remove_all_from_grouping(filter_data, grouping_object, request)
            else:
                targets_ids = request.POST.getlist('selected-target')
                remove_selected_from_grouping(targets_ids, grouping_object, request)
        return redirect(reverse('tom_targets:list') + '?' + query_string)


class TargetGroupingView(PermissionListMixin, ListView):
    """
    View that handles the display of ``TargetList`` objects, also known as target groups. Requires authorization.
    """
    permission_required = 'tom_targets.view_targetlist'
    template_name = 'tom_targets/target_grouping.html'
    model = TargetList
    paginate_by = 25


class TargetGroupingDeleteView(Raise403PermissionRequiredMixin, DeleteView):
    """
    View that handles the deletion of ``TargetList`` objects, also known as target groups. Requires authorization.
    """
    permission_required = 'tom_targets.delete_targetlist'
    model = TargetList
    success_url = reverse_lazy('targets:targetgrouping')


class TargetGroupingCreateView(LoginRequiredMixin, CreateView):
    """
    View that handles the creation of ``TargetList`` objects, also known as target groups. Requires authentication.
    """
    model = TargetList
    fields = ['name']
    success_url = reverse_lazy('targets:targetgrouping')

    def form_valid(self, form):
        """
        Runs after form validation. Saves the target group and assigns the user's permissions to the group.

        :param form: Form data for target creation
        :type form: django.forms.ModelForm
        """
        obj = form.save(commit=False)
        obj.save()
        assign_perm('tom_targets.view_targetlist', self.request.user, obj)
        assign_perm('tom_targets.change_targetlist', self.request.user, obj)
        assign_perm('tom_targets.delete_targetlist', self.request.user, obj)
        return super().form_valid(form)
