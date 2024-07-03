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
from django.db.models import Q
from django.http import HttpResponseRedirect, QueryDict, StreamingHttpResponse, HttpResponseBadRequest
from django.forms import HiddenInput
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.list import ListView
from django.views.generic import RedirectView, TemplateView, View
from django_filters.views import FilterView

from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user, get_groups_with_perms, assign_perm

from tom_common.hints import add_hint
from tom_common.hooks import run_hook
from tom_common.mixins import Raise403PermissionRequiredMixin
from tom_observations.observation_template import ApplyObservationTemplateForm
from tom_observations.models import ObservationTemplate
from tom_targets.filters import TargetFilter
from tom_targets.forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset
from tom_targets.forms import TargetNamesFormset, TargetShareForm, TargetListShareForm
from tom_targets.sharing import share_target_with_tom
from tom_dataproducts.sharing import (share_data_with_hermes, share_data_with_tom, sharing_feedback_handler,
                                      share_target_list_with_hermes)
from tom_dataproducts.models import ReducedDatum
from tom_targets.groups import (
    add_all_to_grouping, add_selected_to_grouping, remove_all_from_grouping, remove_selected_from_grouping,
    move_all_to_grouping, move_selected_to_grouping
)
from tom_targets.models import Target, TargetList
from tom_targets.utils import import_targets, export_targets
from tom_dataproducts.alertstreams.hermes import BuildHermesMessage, preload_to_hermes


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
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.view_target'
    ordering = ['-created']

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


class TargetNameSearchView(RedirectView):
    """
    View for searching by target name. If the search returns one result, the view redirects to the corresponding
    TargetDetailView. Otherwise, the view redirects to the TargetListView.
    """

    def get(self, request, *args, **kwargs):
        target_name = self.kwargs['name']
        # Tests fail without distinct but it works in practice, it is unclear as to why
        # The Django query planner shows different results between in practice and unit tests
        # django-guardian related querying is present in the test planner, but not in practice
        targets = get_objects_for_user(request.user, f'{Target._meta.app_label}.view_target').filter(
            Q(name__icontains=target_name) | Q(aliases__name__icontains=target_name)
        ).distinct()
        if targets.count() == 1:
            return HttpResponseRedirect(reverse('targets:detail', kwargs={'pk': targets.first().id}))
        else:
            return HttpResponseRedirect(reverse('targets:list') + f'?name={target_name}')


class TargetCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating a Target. Requires authentication.
    """

    # Target Views require explicit template names since the Model Class names are variable.
    template_name = 'tom_targets/target_form.html'
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
        # Give the user access to the target they created
        self.object.give_user_access(self.request.user)
        # Run the target post save hook
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
    template_name = 'tom_targets/target_form.html'
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.change_target'
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
        super().form_valid(form)
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
        return redirect(self.get_success_url())

    def get_queryset(self, *args, **kwargs):
        """
        Returns the queryset that will be used to look up the Target by limiting the result to targets that the user is
        authorized to modify.

        :returns: Set of targets
        :rtype: QuerySet
        """
        return get_objects_for_user(self.request.user, f'{Target._meta.app_label}.change_target')

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
    template_name = 'tom_targets/target_confirm_delete.html'
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.delete_target'
    success_url = reverse_lazy('targets:list')
    model = Target


class TargetShareView(FormView):
    """
    View for sharing a target. Requires authorization.
    """
    template_name = 'tom_targets/target_share.html'
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.share_target'
    form_class = TargetShareForm

    def get_context_data(self, *args, **kwargs):
        """
        Adds the target information to the context.
        :returns: context object
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        target_id = self.kwargs.get('pk', None)
        target = Target.objects.get(id=target_id)
        context['target'] = target

        initial = {
            'submitter': self.request.user,
            'share_title': f'Updated data for {target.name}'
        }
        form = TargetShareForm(initial=initial)
        context['form'] = form

        # Add into the context whether hermes-sharing is setup or not
        sharing = getattr(settings, "DATA_SHARING", None)
        if sharing and sharing.get('hermes', {}).get('HERMES_API_KEY'):
            context['hermes_sharing'] = True
        else:
            context['hermes_sharing'] = False

        return context

    def get_success_url(self):
        """
        Redirect to target detail page for shared target
        """
        return reverse_lazy('targets:detail', kwargs={'pk': self.kwargs.get('pk', None)})

    def form_invalid(self, form):
        """
        Adds errors to Django messaging framework in the case of an invalid form and redirects to the previous page.
        """
        # TODO: Format error messages in a more human-readable way
        messages.error(self.request, 'There was a problem sharing your Data: {}'.format(form.errors.as_json()))
        return redirect(self.get_success_url())

    def form_valid(self, form):
        """
        Shares the target with the selected destination(s) and redirects to the target detail page.
        """
        form_data = form.cleaned_data
        share_destination = form_data['share_destination']
        target_id = self.kwargs.get('pk', None)
        selected_data = self.request.POST.getlist("share-box")
        if 'HERMES' in share_destination.upper():
            response = share_data_with_hermes(share_destination, form_data, None, target_id, selected_data)
            sharing_feedback_handler(response, self.request)
        else:
            # Share Target with Destination TOM
            response = share_target_with_tom(share_destination, form_data)
            sharing_feedback_handler(response, self.request)
            if selected_data:
                # Share Data with Destination TOM
                response = share_data_with_tom(share_destination, form_data, selected_data=selected_data)
                sharing_feedback_handler(response, self.request)
        return redirect(self.get_success_url())


class TargetDetailView(Raise403PermissionRequiredMixin, DetailView):
    """
    View that handles the display of the target details. Requires authorization.
    """
    template_name = 'tom_targets/target_detail.html'
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.view_target'
    model = Target

    def get_context_data(self, *args, **kwargs):
        """
        Adds the ``DataProductUploadForm`` to the context and prepopulates the hidden fields.

        :returns: context object
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        observation_template_form = ApplyObservationTemplateForm(initial={'target': self.get_object()})
        if any(self.request.GET.get(x) for x in ['observation_template', 'cadence_strategy', 'cadence_frequency']):
            initial = {'target': self.object}
            initial.update(self.request.GET)
            observation_template_form = ApplyObservationTemplateForm(
                initial=initial
            )
        observation_template_form.fields['target'].widget = HiddenInput()
        context['observation_template_form'] = observation_template_form
        context['target'] = self.object
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
            return redirect(reverse('tom_targets:detail', args=(target_id,)) + '?tab=observations')

        obs_template_form = ApplyObservationTemplateForm(request.GET)
        if obs_template_form.is_valid():
            obs_template = ObservationTemplate.objects.get(pk=obs_template_form.cleaned_data['observation_template'].id)
            obs_template_params = obs_template.parameters
            obs_template_params['cadence_strategy'] = request.GET.get('cadence_strategy', '')
            obs_template_params['cadence_frequency'] = request.GET.get('cadence_frequency', '')
            params = urlencode(obs_template_params)
            return redirect(
                reverse('tom_observations:create',
                        args=(obs_template.facility,)) + f'?target_id={self.get_object().id}&' + params)

        return super().get(request, *args, **kwargs)


class TargetHermesPreloadView(SingleObjectMixin, View):
    model = Target
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.share_target'

    def post(self, request, *args, **kwargs):
        target = self.get_object()
        sharing = getattr(settings, "DATA_SHARING", None)
        if sharing and sharing.get('hermes', {}).get('HERMES_API_KEY'):
            topic = request.POST.get('share_destination', '').split(':')[-1]
            title = request.POST.get('share_title', '')
            if not title:
                title = f'Updated data for {target.name}'
            hermes_message = BuildHermesMessage(
                title=title,
                topic=topic,
                submitter=request.POST.get('submitter'),
                message=request.POST.get('share_message', ''),
                authors=sharing['hermes'].get('DEFAULT_AUTHORS')
            )
            reduced_datums = ReducedDatum.objects.filter(pk__in=request.POST.getlist('share-box', []))
            preload_key = preload_to_hermes(hermes_message, reduced_datums, [target])
            load_url = sharing['hermes']['BASE_URL'] + f'submit-message?id={preload_key}'
            return HttpResponseRedirect(load_url)
        else:
            return HttpResponseBadRequest("Must have hermes section with HERMES_API_KEY set in DATA_SHARING settings")


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
        for target in result['targets']:
            target.give_user_access(request.user)
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
        if 'move' in request.POST:
            if request.POST.get('isSelectAll') == 'True':
                move_all_to_grouping(filter_data, grouping_object, request)
            else:
                target_ids = request.POST.getlist('selected-target')
                move_selected_to_grouping(target_ids, grouping_object, request)

        return redirect(reverse('tom_targets:list') + '?' + query_string)


class TargetGroupingView(PermissionListMixin, ListView):
    """
    View that handles the display of ``TargetList`` objects, also known as target groups. Requires authorization.
    """
    permission_required = 'tom_targets.view_targetlist'
    template_name = 'tom_targets/target_grouping.html'
    model = TargetList
    paginate_by = 25

    def get_context_data(self, *args, **kwargs):
        """
        Adds ``settings.DATA_SHARING`` to the context to see if sharing has been configured.
        :returns: context object
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        context['sharing'] = getattr(settings, "DATA_SHARING", None)
        return context


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


class TargetGroupingShareView(FormView):
    """
    View for sharing a TargetList. Requires authorization.
    """
    template_name = 'tom_targets/target_group_share.html'
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.share_target'
    form_class = TargetListShareForm

    def get_context_data(self, *args, **kwargs):
        """
        Adds the ``TargetListShareForm`` to the context and prepopulates the hidden fields.
        :returns: context object
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        target_list_id = self.kwargs.get('pk', None)
        target_list = TargetList.objects.get(id=target_list_id)
        context['target_list'] = target_list
        initial = {'submitter': self.request.user,
                   'target_list': target_list,
                   'share_title': f"Updated targets for group {target_list.name}."}
        form = TargetListShareForm(initial=initial)
        context['form'] = form

        # Add into the context whether hermes-sharing is setup or not
        sharing = getattr(settings, "DATA_SHARING", None)
        if sharing and sharing.get('hermes', {}).get('HERMES_API_KEY'):
            context['hermes_sharing'] = True
        else:
            context['hermes_sharing'] = False

        return context

    def get_success_url(self):
        """
        Redirects to the target list page with the target list name as a query parameter.
        """
        return reverse_lazy('targets:list')+f'?targetlist__name={self.kwargs.get("pk", None)}'

    def form_invalid(self, form):
        """
        Adds errors to Django messaging framework in the case of an invalid form and redirects to the previous page.
        """
        # TODO: Format error messages in a more human-readable way
        messages.error(self.request, 'There was a problem sharing your Target List: {}'.format(form.errors.as_json()))
        return redirect(self.get_success_url())

    def form_valid(self, form):
        form_data = form.cleaned_data
        share_destination = form_data['share_destination']
        selected_targets = self.request.POST.getlist('selected-target')
        data_switch = self.request.POST.get('dataSwitch', False)
        if 'hermes' in share_destination.lower():
            response = share_target_list_with_hermes(
                share_destination, form_data, selected_targets, include_all_data=data_switch)
            sharing_feedback_handler(response, self.request)
        else:
            for target in selected_targets:
                # Share each target individually
                form_data['target'] = Target.objects.get(id=target)
                response = share_target_with_tom(share_destination, form_data, target_lists=[form_data['target_list']])
                sharing_feedback_handler(response, self.request)
                if data_switch:
                    # If Data sharing request, share all data associated with the target
                    response = share_data_with_tom(share_destination, form_data, target_id=target)
                    sharing_feedback_handler(response, self.request)
            if not selected_targets:
                messages.error(self.request, f'No targets shared. {form.errors.as_json()}')
                return redirect(self.get_success_url())
        return redirect(self.get_success_url())


class TargetGroupingHermesPreloadView(SingleObjectMixin, View):
    model = TargetList
    # Set app_name for Django-Guardian Permissions in case of Custom Target Model
    permission_required = f'{Target._meta.app_label}.share_target'

    def post(self, request, *args, **kwargs):
        targetlist = self.get_object()
        sharing = getattr(settings, "DATA_SHARING", None)
        if sharing and sharing.get('hermes', {}).get('HERMES_API_KEY'):
            topic = request.POST.get('share_destination', '').split(':')[-1]
            title = request.POST.get('share_title', '')
            if not title:
                title = f'Updated targets for group {targetlist.name}.'
            hermes_message = BuildHermesMessage(
                title=title,
                topic=topic,
                submitter=request.POST.get('submitter'),
                message=request.POST.get('share_message', ''),
                authors=sharing['hermes'].get('DEFAULT_AUTHORS')
            )
            targets = Target.objects.filter(pk__in=request.POST.getlist('selected-target', []))
            if request.POST.get('dataSwitch', '') == 'on':
                reduced_datums = ReducedDatum.objects.filter(target__in=targets, data_type='photometry')
            else:
                reduced_datums = ReducedDatum.objects.none()
            preload_key = preload_to_hermes(hermes_message, reduced_datums, targets)
            load_url = sharing['hermes']['BASE_URL'] + f'submit-message?id={preload_key}'
            return HttpResponseRedirect(load_url)
        else:
            return HttpResponseBadRequest("Must have hermes section with HERMES_API_KEY set in DATA_SHARING settings")
