from copy import deepcopy
import json
import logging
from requests import HTTPError
from typing import List

from django.views.generic.edit import DeleteView, FormMixin, FormView, ProcessFormView
from django.views.generic.base import TemplateView, View
from django.db import IntegrityError
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.cache import cache
from guardian.shortcuts import assign_perm
from django_filters.views import FilterView
from django_filters import FilterSet, ChoiceFilter, CharFilter

from tom_alerts.alerts import get_service_class, get_service_classes
from tom_alerts.models import BrokerQuery
from tom_alerts.exceptions import AlertSubmissionException

logger = logging.getLogger(__name__)


class BrokerQueryCreateView(LoginRequiredMixin, FormView):
    """
    View for creating a new query to a broker. Requires authentication.
    """
    template_name = 'tom_alerts/query_form.html'

    def get_broker_name(self):
        """
        Returns the broker specified in the request

        :returns: Broker name
        :rtype: str
        """
        if self.request.method == 'GET':
            return self.request.GET.get('broker')
        elif self.request.method == 'POST':
            return self.request.POST.get('broker')

    def get_form_class(self):
        """
        Returns the form class to use in this view. The form class will be the one defined in the specific broker
        module for which a new query is being created.
        """
        broker_name = self.get_broker_name()

        if not broker_name:
            raise ValueError('Must provide a broker name')

        return get_service_class(broker_name).form

    def get_form(self, form_class=None):
        """
        Returns an instance of the form to be used in this view.

        :returns: Form instance
        :rtype: django.forms.Form
        """
        form = super().get_form()
        form.helper.form_action = reverse('tom_alerts:create')
        return form

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.

        :returns: dict of initial values
        :rtype: dict
        """
        initial = super().get_initial()
        initial['broker'] = self.get_broker_name()
        return initial

    def form_valid(self, form):
        """
        Saves the associated ``BrokerQuery`` and redirects to the ``BrokerQuery`` list.
        """
        form.save()
        return redirect(reverse('tom_alerts:list'))


class BrokerQueryUpdateView(LoginRequiredMixin, FormView):
    """
    View that handles the modification of a previously saved ``BrokerQuery``. Requires authentication.
    """
    template_name = 'tom_alerts/query_form.html'

    def get_object(self):
        """
        Returns the ``BrokerQuery`` object that corresponds with the ID in the query path.

        :returns: ``BrokerQuery`` object
        :rtype: ``BrokerQuery``
        """
        return BrokerQuery.objects.get(pk=self.kwargs['pk'])

    def get_form_class(self):
        """
        Returns the form class to use in this view. The form class will be the one defined in the specific broker
        module for which the query is being updated.
        """
        self.object = self.get_object()
        return get_service_class(self.object.broker).form

    def get_form(self, form_class=None):
        """
        Returns an instance of the form to be used in this view.

        :returns: Form instance
        :rtype: django.forms.Form
        """
        form = super().get_form()
        form.helper.form_action = reverse(
            'tom_alerts:update', kwargs={'pk': self.object.id}
        )
        return form

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view. Initial data for this form consists of the name of
        the broker that the query is for.

        :returns: dict of initial values
        :rtype: dict
        """
        initial = super().get_initial()
        initial.update(self.object.parameters)
        initial['broker'] = self.object.broker
        return initial

    def form_valid(self, form):
        """
        Saves the associated ``BrokerQuery`` and redirects to the ``BrokerQuery`` list.
        """
        form.save(query_id=self.object.id)
        return redirect(reverse('tom_alerts:list'))


class BrokerQueryFilter(FilterSet):
    """
    Defines the available fields for filtering the list of broker queries.
    """
    broker = ChoiceFilter(
        choices=[(k, k) for k in get_service_classes().keys()]
    )
    name = CharFilter(lookup_expr='icontains')

    class Meta:
        model = BrokerQuery
        fields = ['broker', 'name']


class BrokerQueryListView(FilterView):
    """
    View that displays all saved ``BrokerQuery`` objects.
    """
    model = BrokerQuery
    template_name = 'tom_alerts/brokerquery_list.html'
    filterset_class = BrokerQueryFilter

    def get_context_data(self, *args, **kwargs):
        """
        Adds the brokers available to the TOM to the context dictionary.

        :returns: context
        :rtype: dict
        """
        context = super().get_context_data(*args, **kwargs)
        context['installed_brokers'] = get_service_classes()
        return context


class BrokerQueryDeleteView(LoginRequiredMixin, DeleteView):
    """
    View that handles the deletion of a saved ``BrokerQuery``. Requires authentication.
    """
    model = BrokerQuery
    success_url = reverse_lazy('tom_alerts:list')


class RunQueryView(TemplateView):
    """
    View that handles the running of a specific ``BrokerQuery``.
    """
    template_name = 'tom_alerts/query_result.html'

    def get_template_names(self) -> List[str]:
        """Override the base class method to ask the broker if it has
        specified a Broker-specific template to use. If so, put it at the
        front of the returned list of template_names.
        """
        template_names = super().get_template_names()

        # if the broker class has defined a template to use add it to template names (at the front)
        query = get_object_or_404(BrokerQuery, pk=self.kwargs['pk'])
        broker_class = get_service_class(query.broker)()
        logger.debug(f'RunQueryView.get_template_name broker_class: {broker_class}')

        try:
            if broker_class.template_name:
                # add to front of list b/c first template will be tried first
                template_names.insert(0, broker_class.template_name)
        except AttributeError:
            # many Brokers won't have a template_name defined and will just
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

        # get the Broker class
        query = get_object_or_404(BrokerQuery, pk=self.kwargs['pk'])
        broker_class = get_service_class(query.broker)()

        # Do query and get query results (fetch_alerts)
        # TODO: Should the deepcopy be in the brokers?
        try:
            alert_query_results = broker_class.fetch_alerts(deepcopy(query.parameters))

            # Check if feedback is available for fetch_alerts, and allow for backwards compatibility if not.
            if isinstance(alert_query_results, tuple):
                alerts, broker_feedback = alert_query_results
            else:
                alerts = alert_query_results
                broker_feedback = ''
        except AttributeError:
            # If the broker isn't configured in settings.py, display error instead of query results
            alerts = iter(())
            broker_help = getattr(broker_class, 'help_url',
                                  'https://tom-toolkit.readthedocs.io/en/latest/api/tom_alerts/brokers.html')
            broker_feedback = f"""The {broker_class.name} Broker is not properly configured in settings.py.
                                </br>
                                Please see the <a href="{broker_help}" target="_blank">documentation</a> for more
                                information.
                                """
        except HTTPError as e:
            alerts = iter(())
            broker_feedback = f"Issue fetching alerts, please try again.</br>{e}"

        # Post-query tasks
        query.last_run = timezone.now()
        query.save()

        # create context for template
        context['query'] = query
        context['score_description'] = broker_class.score_description
        context['broker_feedback'] = broker_feedback

        context['alerts'] = []
        try:
            while True:
                alert = next(alerts)
                generic_alert = broker_class.to_generic_alert(alert)
                cache.set(f'alert_{generic_alert.id}', json.dumps(alert), 3600)
                context['alerts'].append(generic_alert)
        except StopIteration:
            pass

        # allow the Broker to add to the context (besides the query_results)
        broker_context_additions = broker_class.get_broker_context_data(alerts)
        context.update(broker_context_additions)
        # TODO: in python 3.9 we could use the merge operator context |= broker_dict
        # context |= broker_context_additions

        return context


class CreateTargetFromAlertView(LoginRequiredMixin, View):
    """
    View that handles the creation of ``Target`` objects from a ``BrokerQuery`` result. Requires authentication.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles the POST requests to this view. Creates a ``Target`` for each alert sent in the POST. Redirects to the
        ``TargetListView`` if multiple targets were created, and the ``TargetUpdateView`` if only one was created.
        Redirects to the ``RunQueryView`` if no ``Target`` objects. were successfully created.
        """
        query_id = self.request.POST['query_id']
        broker_name = self.request.POST['broker']
        broker_class = get_service_class(broker_name)
        alerts = self.request.POST.getlist('alerts')
        errors = []
        if not alerts:
            messages.warning(request, 'Please select at least one alert from which to create a target.')
            return redirect(reverse('tom_alerts:run', kwargs={'pk': query_id}))
        for alert_id in alerts:
            cached_alert = cache.get('alert_{}'.format(alert_id))
            if not cached_alert:
                messages.error(request, 'Could not create targets. Try re running the query again.')
                return redirect(reverse('tom_alerts:run', kwargs={'pk': query_id}))
            generic_alert = broker_class().to_generic_alert(json.loads(cached_alert))
            target, extras, aliases = generic_alert.to_target()
            try:
                target.save(extras=extras, names=aliases)
                # Give the user access to the target they created
                target.give_user_access(self.request.user)
                broker_class().process_reduced_data(target, json.loads(cached_alert))
                for group in request.user.groups.all().exclude(name='Public'):
                    assign_perm('tom_targets.view_target', group, target)
                    assign_perm('tom_targets.change_target', group, target)
                    assign_perm('tom_targets.delete_target', group, target)
            except IntegrityError:
                messages.warning(request, f'Unable to save {target.name}, target with that name already exists.')
                errors.append(target.name)
        if len(alerts) == len(errors):
            return redirect(reverse('tom_alerts:run', kwargs={'pk': query_id}))
        return redirect(reverse('tom_targets:list'))


class SubmitAlertUpstreamView(LoginRequiredMixin, FormMixin, ProcessFormView, View):
    """
    View used to submit alerts to an upstream broker, such as SCIMMA's Hopskotch or the Transient Name Server.

    While this view handles the query parameters for target_id and observation_record_id by default, it will
    send any additional query parameters to the broker, allowing a broker to use any arbitrary parameters.
    """

    def get_broker_name(self):
        return self.kwargs['broker']

    def get_form_class(self):
        broker_name = self.get_broker_name()
        return get_service_class(broker_name).alert_submission_form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'broker': self.get_broker_name()
        })

        return kwargs

    def get_redirect_url(self):
        """
        If ``next`` is provided in the query params, redirects to ``next``. If ``HTTP_REFERER`` is present on the
        ``META`` property of the request, redirects to ``HTTP_REFERER``. Else redirects to /.

        :returns: url to redirect to
        :rtype: str
        """
        next_url = self.request.POST.get('redirect_url')
        redirect_url = next_url if next_url else self.request.META.get('HTTP_REFERER')
        if not redirect_url:
            redirect_url = reverse('home')

        return redirect_url

    def form_invalid(self, form):
        logger.log(msg=f'Form invalid: {form.errors}', level=logging.WARN)
        messages.warning(self.request,
                         f'Unable to submit one or more alerts to {self.get_broker_name()}. See logs for details.')
        return redirect(self.get_redirect_url())

    def form_valid(self, form):
        broker_name = self.get_broker_name()
        broker = get_service_class(broker_name)()

        target = form.cleaned_data.pop('target')
        obsr = form.cleaned_data.pop('observation_record')
        form.cleaned_data.pop('redirect_url')  # redirect_url doesn't need to be passed to submit_upstream_alert

        try:
            # Pass non-standard fields from query parameters as kwargs
            success = broker.submit_upstream_alert(target=target, observation_record=obsr, **form.cleaned_data)
        except AlertSubmissionException as e:
            logger.log(msg=f'Failed to submit alert: {e}', level=logging.WARN)
            success = False

        if success:
            messages.success(self.request, f'Successfully submitted alerts to {broker_name}!')
        else:
            messages.warning(self.request,
                             f'Unable to submit one or more alerts to {self.get_broker_name()}. See logs for details.')

        return redirect(self.get_redirect_url())
