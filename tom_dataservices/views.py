from django_filters.views import FilterView
from django_filters import FilterSet, ChoiceFilter, CharFilter
from django.views.generic.edit import DeleteView, FormMixin, FormView, ProcessFormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse

from tom_dataservices.models import DataServiceQuery
from tom_dataservices.dataservices import get_data_service_classes, get_data_service_class


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

        :returns: Broker name
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
            raise ValueError('Must provide a broker name')

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
        form.save()
        return redirect(reverse('tom_dataservices:query_list'))
