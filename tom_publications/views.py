from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationGroup
from tom_publications.forms import LatexTableForm
from tom_publications.latex import get_latex_processor
from tom_publications.models import LatexConfiguration
from tom_targets.models import TargetList


class LatexTableView(LoginRequiredMixin, TemplateView):
    template_name = 'tom_publications/latex_table.html'

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)

        model_name = request.GET.get('model_name')
        model_pk = request.GET.get('model_pk')
        field_list = request.GET.getlist('field_list', None)
        obj = None
        if not model_name:
            raise Exception
        else:
            model = apps.get_model(model_name)
            obj = model.objects.get(pk=request.GET.get('model_pk'))

        processor = get_latex_processor(model_name.split('.')[1])

        latex = []
        if not field_list:
            latex_form = processor.get_form(initial={
                'model_pk': model_pk,
                'model_name': model_name,
                'field_list': []
            })
        else:
            latex_form = processor.get_form({
                'model_pk': model_pk,
                'model_name': model_name,
                'field_list': field_list,
            })
            if latex_form.is_valid():
                latex_form.clean()
                print('cleaned')
                print(latex_form.cleaned_data)
                print(latex_form.cleaned_data['field_list'])

                latex = processor.create_latex(
                    latex_form.cleaned_data['model_pk'],
                    latex_form.cleaned_data['field_list']
                )
                # print(ascii.write(latex, format='latex'))
                print(latex)
                if request.GET.get('save-latex'):
                    config = LatexConfiguration(
                        fields=','.join(latex_form.cleaned_data['field_list']),
                        model_name=latex_form.cleaned_data['model_name']
                    )
                    config.save()

        context['object'] = obj
        context['latex_form'] = latex_form
        context['latex'] = latex

        return self.render_to_response(context)
