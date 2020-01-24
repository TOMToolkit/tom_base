from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationGroup
from tom_publications.forms import LatexTableForm, LatexConfigurationForm
from tom_targets.models import TargetList


class LatexTableView(LoginRequiredMixin, TemplateView):
    template_name = 'tom_publications/latex_table.html'

    # def get_object(self):
    #     # obj = self.request.GET.get('model')
    #     model_type = self.request.GET.get('model_type')
    #     model_pk = self.request.GET.get('model_pk')

    #     for app in apps.get_app_configs():
    #         try:
    #             model = apps.get_model(app.label, model_type)
    #         except LookupError:
    #             pass

    #     self.object = model.objects.get(pk=model_pk)
    #     return self.object

    # def get_context_data(self, *args, **kwargs):
    #     context = super().get_context_data(*args, **kwargs)
    #     if self.request.method == 'GET':
    #         model_name = self.request.GET.get('model_name')
    #         model_pk = self.request.GET.get('model_pk')
    #         field_list = self.request.GET.get('field_list')

    #         print(field_list)

    #         # processor = get_latex_processor(model_name)
    #         # print(processor)

    #         print(model_name)

    #         form = GenericLatexForm(model_name, model_pk, field_list=field_list)

    #         context['form'] = kwargs.get('form')
    #         print(form.fields)
    #         # print(form)

    #     return context

    # def get(self, request, *args, **kwargs):
    #     latex_form = GenericLatexForm(initial=request.GET)
    #     if latex_form.is_valid():
    #         table = []

    #     kwargs['form'] = latex_form
    #     kwargs['table'] = table
    #     context = self.get_context_data(**kwargs)
    #     return self.render_to_response(context)

    # def post(self, request, *args, **kwargs):
    #     latex_save_form = LatexSaveForm(request.POST)
    #     if latex_save_form.is_valid():
    #         pass

    #     return super().get(request, *args, **kwargs)


class SaveLatexConfigurationView(LoginRequiredMixin, FormView):
    form_class = LatexConfigurationForm
    template_name = 'tom_publications/latex_table.html'


# class LatexTableView(LoginRequiredMixin, FormView):
#     form_class = LatexTableObjectForm
#     template_name = 'tom_dataproducts/latex_table.html'
#     success_url = reverse_lazy('tom_dataproducts:latex-table-create')

#     def get_initial(self):
#         initial = super().get_initial()
#         if self.request.method == 'GET':
#             initial['model_pk'] = self.request.GET.get('model_pk')
#             initial['model_type'] = self.request.GET.get('model_type')
#         elif self.request.method == 'POST':
#             initial['model_pk'] = self.request.POST.get('model_pk')
#             initial['model_type'] = self.request.POST.get('model_type')
#         return initial

#     def get(self, request, *args, **kwargs):
#         # print(self.get_form())
#         print('get')
#         print(request.GET)
#         return super().get(request, args, kwargs)

#     def form_valid(self, form):
#         print('form_valid')
#         obj = {}
#         if form.cleaned_data['model_type'] == 'target':
#             obj = Target.objects.get(id=form.cleaned_data['model_pk'])
#         elif form.cleaned_data['model_type'] == 'target_list':
#             obj = TargetList.objects.get(id=form.cleaned_data['model_pk'])
#         elif form.cleaned_data['model_type'] == 'observation_record':
#             obj = ObservationRecord.objects.get(id=form.cleaned_data['model_pk'])
#         elif form.cleaned_data['model_type'] == 'datum':
#             obj = ReducedDatum.objects.get(id=form.cleaned_data['model_pk'])

#         table_data = {}
#         column_names = []
#         print(obj)
#         for field in form.cleaned_data['target_fields']:
#             table_data[field] = getattr(obj, field)
#             column_names.append(field)
#         print(table_data)
#         print(column_names)

#         return super().form_valid(form)

#     def form_invalid(self, form):
#         print(form.errors)
#         return super().form_invalid(form)

#     # def post(self, request, *args, **kwargs):
#     #     print('post')
#     #     print(request.POST)
#     #     return super().post(request, *args, **kwargs)
