from django.views.generic.edit import FormView, DeleteView
from django.views.generic.base import TemplateView, View
from tom_alerts.alerts import get_service_class, get_service_classes
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from guardian.shortcuts import assign_perm
import django_filters

from tom_alerts.models import BrokerQuery


class BrokerQueryCreateView(LoginRequiredMixin, FormView):
    template_name = 'tom_alerts/query_form.html'

    def get_broker_name(self):
        if self.request.method == 'GET':
            return self.request.GET.get('broker')
        elif self.request.method == 'POST':
            return self.request.POST.get('broker')

    def get_form_class(self):
        broker_name = self.get_broker_name()

        if not broker_name:
            raise ValueError('Must provide a broker name')

        return get_service_class(broker_name).form

    def get_form(self):
        form = super().get_form()
        form.helper.form_action = reverse('tom_alerts:create')
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial['broker'] = self.get_broker_name()
        return initial

    def form_valid(self, form):
        form.save()
        return redirect(reverse('tom_alerts:list'))


class BrokerQueryUpdateView(LoginRequiredMixin, FormView):
    template_name = 'tom_alerts/query_form.html'

    def get_object(self):
        return BrokerQuery.objects.get(pk=self.kwargs['pk'])

    def get_form_class(self):
        self.object = self.get_object()
        return get_service_class(self.object.broker).form

    def get_form(self):
        form = super().get_form()
        form.helper.form_action = reverse(
            'tom_alerts:update', kwargs={'pk': self.object.id}
        )
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.object.parameters_as_dict)
        initial['broker'] = self.object.broker
        return initial

    def form_valid(self, form):
        form.save(query_id=self.object.id)
        return redirect(reverse('tom_alerts:list'))


class BrokerQueryFilter(django_filters.FilterSet):
    broker = django_filters.ChoiceFilter(
        choices=[(k, k) for k in get_service_classes().keys()]
    )
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = BrokerQuery
        fields = ['broker', 'name']


class BrokerQueryListView(django_filters.views.FilterView):
    model = BrokerQuery
    template_name = 'tom_alerts/brokerquery_list.html'
    filterset_class = BrokerQueryFilter

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['installed_brokers'] = get_service_classes()
        return context


class BrokerQueryDeleteView(LoginRequiredMixin, DeleteView):
    model = BrokerQuery
    success_url = reverse_lazy('tom_alerts:list')


class RunQueryView(TemplateView):
    template_name = 'tom_alerts/query_result.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data()
        query = get_object_or_404(BrokerQuery, pk=self.kwargs['pk'])
        broker_class = get_service_class(query.broker)()
        alerts = broker_class.fetch_alerts(query.parameters_as_dict)
        context['alerts'] = [
            broker_class.to_generic_alert(alert) for alert in alerts
        ]
        context['query'] = query
        return context


class CreateTargetFromAlertView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        query_id = self.request.POST['query_id']
        broker_name = self.request.POST['broker']
        broker_class = get_service_class(broker_name)
        alerts = self.request.POST.getlist('alerts')
        if not alerts:
            messages.warning(request, 'Please select at least one alert from which to create a target.')
            return redirect(reverse('tom_alerts:run', kwargs={'pk': query_id}))
        for alert in alerts:
            alert = broker_class().fetch_alert(alert)
            target = broker_class().to_target(alert)
            broker_class().process_reduced_data(target, alert)
            target.save()
            for group in request.user.groups.all().exclude(name='Public'):
                assign_perm('tom_targets.view_target', group, target)
                assign_perm('tom_targets.change_target', group, target)
                assign_perm('tom_targets.delete_target', group, target)
        if (len(alerts) == 1):
            return redirect(reverse(
                'tom_targets:update', kwargs={'pk': target.id})
            )
        else:
            return redirect(reverse(
                'tom_targets:list')
            )
