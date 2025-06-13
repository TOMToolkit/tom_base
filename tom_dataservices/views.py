from typing import List
import logging

from django_filters.views import FilterView
from django_filters import FilterSet, ChoiceFilter, CharFilter
from django.views.generic.edit import DeleteView, FormMixin, FormView, ProcessFormView
from django.views.generic.base import TemplateView, View
from django.db import IntegrityError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from guardian.shortcuts import assign_perm
from django.utils import timezone
from django.core.cache import cache
from django.contrib import messages

from tom_dataservices.models import DataServiceQuery
from tom_dataservices.dataservices import get_data_service_classes, get_data_service_class

logger = logging.getLogger(__name__)


class DataServiceQueryFilter(FilterSet):
    """
    Defines the available fields for filtering the list of broker queries.
    """
    broker = ChoiceFilter(
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
        Returns the form class to use in this view. The form class will be the one defined in the specific broker
        module for which a new query is being created.
        """
        data_service_name = self.get_data_service_name()

        if not data_service_name:
            raise ValueError('Must provide a data service name')

        return get_data_service_class(data_service_name).get_form_class(self)

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
        return redirect(reverse('tom_dataservices:query_list'))


class RunQueryView(TemplateView):
    """
    View that handles the running of a specific ``DataServiceQuery``.
    """
    template_name = 'tom_dataservices/query_result.html'

    def get_template_names(self) -> List[str]:
        """Override the base class method to ask the broker if it has
        specified a Broker-specific template to use. If so, put it at the
        front of the returned list of template_names.
        """
        template_names = super().get_template_names()

        # if the data service class has defined a template to use add it to template names (at the front)
        query = get_object_or_404(DataServiceQuery, pk=self.kwargs['pk'])
        data_service_class = get_data_service_class(query.data_service)()
        logger.debug(f'RunQueryView.get_template_name data_service_class: {data_service_class}')

        try:
            if data_service_class.template_name:
                # add to front of list b/c first template will be tried first
                template_names.insert(0, data_service_class.template_name)
        except AttributeError:
            # many Data Services won't have a template_name defined and will just
            # use the one defined above.
            pass

        logger.debug(f'RunQueryView.get_template_name template_names: {template_names}')
        return template_names

    def get_context_data(self, *args, **kwargs):
        """
        Runs the ``fetch_alerts`` method specific to the given ``BrokerQuery`` and adds the matching alerts to the
        context dictionary.

        :returns: context
        :rtype: dict
        """
        context = super().get_context_data()

        # get the DataService class
        query = get_object_or_404(DataServiceQuery, pk=self.kwargs['pk'])
        data_service_class = get_data_service_class(query.data_service)()

        # Do query and get query results (fetch_alerts)
        # try:
        #     query_results = data_service_class.fetch_alerts(deepcopy(query.parameters))
        #
        #     # Check if feedback is available for fetch_alerts, and allow for backwards compatibility if not.
        #     if isinstance(query_results, tuple):
        #         results, query_feedback = query_results
        #     else:
        #         results = query_results
        #         query_feedback = ''
        # except AttributeError:
        #     # If the broker isn't configured in settings.py, display error instead of query results
        #     results = iter(())
        #     broker_help = getattr(data_service_class, 'help_url',
        #                           'https://tom-toolkit.readthedocs.io/en/latest/api/tom_alerts/brokers.html')
        #     query_feedback = f"""The {data_service_class.name} Broker is not properly configured in settings.py.
        #                         </br>
        #                         Please see the <a href="{broker_help}" target="_blank">documentation</a> for more
        #                         information.
        #                         """
        # except HTTPError as e:
        #     results = iter(())
        #     query_feedback = f"Issue fetching alerts, please try again.</br>{e}"

        query_parameters = data_service_class.build_query_parameters(query.parameters)
        results = data_service_class.query_targets(query_parameters)

        # Post-query tasks
        query.last_run = timezone.now()
        query.save()

        # create context for template
        context['query'] = query
        # context['query_feedback'] = query_feedback
        context['too_many_results'] = False

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

        # allow the Broker to add to the context (besides the query_results)
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
        return get_data_service_class(self.object.data_service).get_form_class(self)

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
        Saves the associated ``DataServiceQuery`` and redirects to the ``DataServiceQuery`` list.
        """
        if form.cleaned_data['query_save']:
            form.save(query_id=self.object.id)
        return redirect(reverse('tom_dataservices:query_list'))


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
        if not results:
            messages.warning(request, 'Please select at least one alert from which to create a target.')
            return redirect(reverse('dataservices:run', kwargs={'pk': query_id}))
        for result_id in results:
            cached_result = cache.get(f'result_{result_id}')
            if not cached_result:
                messages.error(request, 'Could not create targets. Try re running the query again.')
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
                messages.warning(request, f'Unable to save {target.name}, target with that name already exists.')
                errors.append(target.name)
        if len(results) == len(errors):
            return redirect(reverse('dataservices:run', kwargs={'pk': query_id}))
        return redirect(reverse('tom_targets:list'))
