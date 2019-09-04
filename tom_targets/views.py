from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic import TemplateView, View
from django_filters.views import FilterView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.http import StreamingHttpResponse
from django.utils.text import slugify
from guardian.mixins import PermissionRequiredMixin, PermissionListMixin
from guardian.shortcuts import get_objects_for_user, get_groups_with_perms, assign_perm
from datetime import datetime
from io import StringIO

from .models import Target, TargetList
from tom_dataproducts.forms import DataProductUploadForm
from .forms import SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset
from .import_targets import import_targets
from .export_targets import export_targets
from .filters import TargetFilter
from .add_remove_from_grouping import add_remove_from_grouping


class TargetListView(PermissionListMixin, FilterView):
    template_name = 'tom_targets/target_list.html'
    paginate_by = 25
    strict = False
    model = Target
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['target_count'] = context['paginator'].count
        # hide target grouping list if user not logged in
        context['groupings'] = (TargetList.objects.all()
                                if self.request.user.is_authenticated
                                else TargetList.objects.none())
        context['query_string'] = self.request.META['QUERY_STRING']
        return context


class TargetCreateView(LoginRequiredMixin, CreateView):
    model = Target
    fields = '__all__'

    def get_default_target_type(self):
        try:
            return settings.TARGET_TYPE
        except AttributeError:
            return Target.SIDEREAL

    def get_initial(self):
        return {
            'type': self.get_default_target_type(),
            'groups': self.request.user.groups.all(),
            **dict(self.request.GET.items())
        }

    def get_context_data(self, **kwargs):
        context = super(TargetCreateView, self).get_context_data(**kwargs)
        context['type_choices'] = Target.TARGET_TYPES
        context['extra_form'] = TargetExtraFormset()
        return context

    def get_form_class(self):
        target_type = self.get_default_target_type()
        if self.request.GET:
            target_type = self.request.GET.get('type', target_type)
        elif self.request.POST:
            target_type = self.request.POST.get('type', target_type)
        if target_type == Target.SIDEREAL:
            self.initial['type'] = Target.SIDEREAL
            return SiderealTargetCreateForm
        elif target_type == Target.NON_SIDEREAL:
            self.initial['type'] = Target.NON_SIDEREAL
            return NonSiderealTargetCreateForm

    def form_valid(self, form):
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST)
        if extra.is_valid():
            extra.instance = self.object
            extra.save()
        return redirect(self.get_success_url())

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        if self.request.user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = self.request.user.groups.all()
        return form


class TargetUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'tom_targets.change_target'
    model = Target
    fields = '__all__'

    def get_context_data(self, **kwargs):
        extra_field_names = [extra['name'] for extra in settings.EXTRA_FIELDS]
        context = super().get_context_data(**kwargs)
        context['extra_form'] = TargetExtraFormset(
            instance=self.object,
            queryset=self.object.targetextra_set.exclude(key__in=extra_field_names)
        )
        return context

    def form_valid(self, form):
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST, instance=self.object)
        if extra.is_valid():
            extra.save()
        return redirect(self.get_success_url())

    def get_queryset(self, *args, **kwargs):
        return get_objects_for_user(self.request.user, 'tom_targets.change_target')

    def get_form_class(self):
        if self.object.type == Target.SIDEREAL:
            return SiderealTargetCreateForm
        elif self.object.type == Target.NON_SIDEREAL:
            return NonSiderealTargetCreateForm

    def get_initial(self):
        initial = super().get_initial()
        initial['groups'] = get_groups_with_perms(self.get_object())
        return initial

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        if self.request.user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = self.request.user.groups.all()
        return form


class TargetDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'tom_targets.delete_target'
    success_url = reverse_lazy('targets:list')
    model = Target


class TargetDetailView(PermissionRequiredMixin, DetailView):
    permission_required = 'tom_targets.view_target'
    model = Target

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        data_product_upload_form = DataProductUploadForm(
            initial={
                'target': self.get_object(),
                'referrer': reverse('tom_targets:detail', args=(self.get_object().id,))
            },
            hide_target_fields=False
        )
        context['data_product_form'] = data_product_upload_form
        return context

    def get(self, request, *args, **kwargs):
        update_status = request.GET.get('update_status', False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            target_id = kwargs.get('pk', None)
            out = StringIO()
            call_command('updatestatus', target_id=target_id, stdout=out)
            messages.info(request, out.getvalue())
            return redirect(reverse('tom_targets:detail', args=(target_id,)))
        return super().get(request, *args, **kwargs)


class TargetImportView(LoginRequiredMixin, TemplateView):
    template_name = 'tom_targets/target_import.html'

    def post(self, request):
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
    def render_to_response(self, context, **response_kwargs):
        qs = context['filter'].qs.values()
        file_buffer = export_targets(qs)
        file_buffer.seek(0)  # goto the beginning of the buffer
        response = StreamingHttpResponse(file_buffer, content_type="text/csv")
        filename = "targets-{}.csv".format(slugify(datetime.utcnow()))
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        return response


class TargetAddRemoveGroupingView(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        query_string = request.POST.get('query_string', '')
        add_remove_from_grouping(request, query_string)
        return redirect(reverse('tom_targets:list') + '?' + query_string)


class TargetGroupingView(PermissionListMixin, ListView):
    permission_required = 'tom_targets.view_targetlist'
    template_name = 'tom_targets/target_grouping.html'
    model = TargetList
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class TargetGroupingDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'tom_targets.delete_targetlist'
    model = TargetList
    success_url = reverse_lazy('targets:targetgrouping')


class TargetGroupingCreateView(LoginRequiredMixin, CreateView):
    model = TargetList
    fields = ['name']
    success_url = reverse_lazy('targets:targetgrouping')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.save()
        assign_perm('tom_targets.view_targetlist', self.request.user, obj)
        assign_perm('tom_targets.change_targetlist', self.request.user, obj)
        assign_perm('tom_targets.delete_targetlist', self.request.user, obj)
        return super().form_valid(form)
