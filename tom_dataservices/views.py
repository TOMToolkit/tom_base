import logging
from requests import HTTPError

from django_filters.views import FilterView
from django_filters import FilterSet, ChoiceFilter, CharFilter
from django.views.generic.edit import DeleteView, FormView
from django.views.generic.base import TemplateView, View
from django.db import IntegrityError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from guardian.shortcuts import assign_perm
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.core.cache import cache
from django.contrib import messages
from urllib.parse import urlencode

from tom_dataservices.models import DataServiceQuery
from tom_dataservices.dataservices import get_data_service_classes, get_data_service_class, NotConfiguredError

logger = logging.getLogger(__name__)


class DataServiceQueryFilter(FilterSet):
    """
    Defines the available fields for filtering the list of queries.
    """
    data_service = ChoiceFilter(
        choices=[(k, k) for k in get_data_service_classes().keys()]
    )
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = DataServiceQuery
        fields = ['data_service', 'name']


class DataServiceQueryListView(FilterView):
    """
    View that displays all saved ``DataServiceQuery`` objects.
    """
    model = DataServiceQuery
    template_name = 'tom_dataservices/query_list.html'
    filterset_class = DataServiceQueryFilter

    def get_context_data(self, *args, **kwargs):
        """
        Adds the data services available to the TOM to the context dictionary.

        :returns: context
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        context['installed_services'] = get_data_service_classes()
        return context


class DataServiceQueryCreateView(LoginRequiredMixin, FormView):
    """
    View for creating a new query to a data service. Requires authentication.
    """
    template_name = 'tom_dataservices/query_form.html'
    success_url = reverse_lazy('tom_dataservices:run')

    def get_data_service_name(self):
        """
        Returns the data service specified in the request

        :returns: DataService name
        :rtype: str
        """
        if self.request.method == 'GET':
            return self.request.GET.get('data_service')
        elif self.request.method == 'POST':
            return self.request.POST.get('data_service')

    def get_form_class(self):
        """
        Returns the form class to use in this view. The form class will be the one defined in the specific dataservice
        module for which a new query is being created.
        """
        data_service_name = self.get_data_service_name()

        if not data_service_name:
            raise ValueError('Must provide a data service name')

        return get_data_service_class(data_service_name).get_form_class()

    def get_form(self, form_class=None):
        """
        Returns an instance of the form to be used in this view.

        :returns: Form instance
        :rtype: django.forms.Form
        """
        form = super().get_form()
        form.helper.form_action = reverse('tom_dataservices:create')
        return form

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.

        :returns: dict of initial values
        :rtype: dict
        """
        initial = super().get_initial()
        initial['data_service'] = self.get_data_service_name()
        return initial

    def form_valid(self, form):
        """
        Saves the associated ``DataServiceQuery`` and redirects to the ``DataServiceQuery`` list.
        """

        if form.cleaned_data['query_save']:
            form.save()

        self.request.session['query_parameters'] = form.cleaned_data

        return redirect(self.success_url)

    def get_context_data(self, *args, **kwargs):
        """
        Adds any form partials to the context.

        :returns: context
        :rtype: dict
        """
        context = super().get_context_data()

        data_service_name = self.get_data_service_name()
        simple_form = get_data_service_class(data_service_name).get_simple_form_partial(self)
        advanced_form = get_data_service_class(data_service_name).get_advanced_form_partial(self)
        context['simple_form'] = simple_form
        context['advanced_form'] = advanced_form
        return context


class RunQueryView(TemplateView):
    """
    View that handles the running of a query that was either submitted via the form or saved as a ``DataServiceQuery``.
    """
    template_name = 'tom_dataservices/query_result.html'

    def get_context_data(self, *args, **kwargs):
        """
        Collects the query parameters from either a saved ``DataServiceQuery`` or from the session data,
        runs the query, and returns the results as context for the list template.

        :returns: context
        :rtype: dict
        """
        context = super().get_context_data()
        query = None
        query_feedback = ""
        data_service_class = None

        # Do query and get query results
        try:
            # get the DataService class. Pull saved query if PK available, otherwise use session data.
            if self.kwargs.get('pk', None) is not None:
                query = get_object_or_404(DataServiceQuery, pk=self.kwargs['pk'])
                data_service_class = get_data_service_class(query.data_service)()
                query_parameters = data_service_class.build_query_parameters(query.parameters)
                query.last_run = timezone.now()
                query.save()
            else:
                input_parameters = self.request.session.get('query_parameters', {})
                data_service_class = get_data_service_class(input_parameters['data_service'])()
                query_parameters = data_service_class.build_query_parameters(input_parameters)

            results = data_service_class.query_targets(query_parameters)
        except HTTPError as e:
            results = iter(())
            query_feedback += f"Issue fetching query results, please try again.</br>{e}</br>"
        except NotConfiguredError as e:
            results = iter(())
            query_feedback += f"Configuration Error. Please contact your TOM Administrator: </br>{e}</br>"

        # create context for template
        context['query'] = query
        context['query_feedback'] = query_feedback
        context['too_many_results'] = False
        context['data_service'] = data_service_class.name
        context['query_results_table'] = data_service_class.query_results_table or 'tom_dataservices/partials/' \
                                                                                   'query_results_table.html'

        context['results'] = []
        try:
            for (i, result) in enumerate(results):
                if i > 99:
                    # issue 1172 too many alerts causes the cache to overflow
                    context['too_many_results'] = True
                    break
                result['id'] = i
                cache.set(f'result_{i}', result, 3600)
                context['results'].append(result)
        except StopIteration:
            pass

        # allow the Data Service to add to the context (besides the query_results)
        data_service_context_additions = data_service_class.get_additional_context_data()
        context |= data_service_context_additions

        return context


class DataServiceQueryDeleteView(LoginRequiredMixin, DeleteView):
    """
    View that handles the deletion of a saved ``DataServiceQuery``. Requires authentication.
    """
    model = DataServiceQuery
    success_url = reverse_lazy('dataservices:query_list')


class DataServiceQueryUpdateView(LoginRequiredMixin, FormView):
    """
    View that handles the modification of a previously saved ``DataServiceQuery``. Requires authentication.
    """
    template_name = 'tom_dataservices/query_form.html'
    success_url = reverse_lazy('tom_dataservices:run')
    object = None

    def get_object(self):
        """
        Returns the ``DataServiceQuery`` object that corresponds with the ID in the query path.

        :returns: ``DataServiceQuery`` object
        :rtype: ``DataServiceQuery``
        """
        return DataServiceQuery.objects.get(pk=self.kwargs['pk'])

    def get_form_class(self):
        """
        Returns the form class to use in this view. The form class will be the one defined in the specific data service
        module for which the query is being updated.
        """
        self.object = self.get_object()
        return get_data_service_class(self.object.data_service).get_form_class()

    def get_form(self, form_class=None):
        """
        Returns an instance of the form to be used in this view.

        :returns: Form instance
        :rtype: django.forms.Form
        """
        form = super().get_form()
        form.helper.form_action = reverse(
            'dataservices:update', kwargs={'pk': self.object.id}
        )
        return form

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view. Initial data for this form consists of the name of
        the Data Service that the query is for and the saved query parameters.

        :returns: dict of initial values
        :rtype: dict
        """
        initial = super().get_initial()
        initial.update(self.object.parameters)
        initial['data_service'] = self.object.data_service
        return initial

    def form_valid(self, form):
        """
        Saves the associated ``DataServiceQuery`` if requested and redirects to the ``DataServiceQuery`` list.
        """
        if form.cleaned_data['query_save']:
            form.save(query_id=self.object.id)
        self.request.session['query_parameters'] = form.cleaned_data
        return redirect(self.success_url)

    def get_context_data(self, *args, **kwargs):
        """
        Adds any form partials to the context.

        :returns: context
        :rtype: dict
        """
        context = super().get_context_data()

        data_service_name = self.object.data_service
        simple_form = get_data_service_class(data_service_name).get_simple_form_partial(self)
        advanced_form = get_data_service_class(data_service_name).get_advanced_form_partial(self)
        context['simple_form'] = simple_form
        context['advanced_form'] = advanced_form
        context['object'] = self.object
        return context


class CreateTargetFromQueryView(LoginRequiredMixin, View):
    """
    View that handles the creation of ``Target`` objects from a Data Service Query result. Requires authentication.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles the POST requests to this view. Creates a ``Target`` for each query result sent in the POST. Redirects
        to the ``TargetListView`` if multiple targets were created, and the ``TargetUpdateView`` if only one was
        created. Redirects to the ``RunQueryView`` if no ``Target`` objects were successfully created.
        """
        query_id = self.request.POST['query_id']
        data_service_name = self.request.POST['data_service']
        data_service_class = get_data_service_class(data_service_name)()
        results = self.request.POST.getlist('selected_results')
        errors = []
        target = None
        if not results:
            messages.warning(request, 'Please select at least one result from which to create a target.')
            return redirect(reverse('dataservices:run', kwargs={'pk': query_id}))
        for result_id in results:
            cached_result = cache.get(f'result_{result_id}')
            if not cached_result:
                messages.error(request, 'Could not create targets. Try re-running the query again.')
                return redirect(reverse('dataservices:run', kwargs={'pk': query_id}))
            target, extras, aliases = data_service_class.to_target(cached_result)
            try:
                target.save(extras=extras, names=aliases)
                # Give the user access to the target they created
                target.give_user_access(self.request.user)
                try:
                    data_service_class.to_reduced_datums(target, cached_result)
                except NotImplementedError:
                    pass
                for group in request.user.groups.all():
                    assign_perm('tom_targets.view_target', group, target)
                    assign_perm('tom_targets.change_target', group, target)
                    assign_perm('tom_targets.delete_target', group, target)
            except IntegrityError:
                messages.warning(request, mark_safe(
                                 f"""Unable to save {target.name}, target with that name already exists.
                                 You can <a href="{reverse('targets:create') + '?' +
                                                   urlencode(target.as_dict())}">create</a>
                                  a new target anyway.
                                 """)
                                 )
                errors.append(target.name)
        if len(results) == len(errors):
            return redirect(reverse('dataservices:run'))
        if len(results) == 1 and target:
            return redirect(reverse('tom_targets:detail', kwargs={'pk': target.id}))
        return redirect(reverse('tom_targets:list'))
