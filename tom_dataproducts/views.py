from urllib.parse import urlparse
from io import StringIO

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView, DeleteView
from django.views.generic.edit import CreateView
from django_filters.views import FilterView
from django.views.generic import View, ListView
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from django.core.management import call_command
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.http import HttpResponseRedirect
from guardian.shortcuts import get_objects_for_user

from .models import DataProduct, DataProductGroup
from .utils import process_data_product
from .forms import AddProductToGroupForm, DataProductUploadForm
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class


class DataProductSaveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        service_class = get_service_class(request.POST['facility'])
        observation_record = ObservationRecord.objects.get(pk=kwargs['pk'])
        products = request.POST.getlist('products')
        if not products:
            messages.warning(request, 'No products were saved, please select at least one dataproduct')
        elif products[0] == 'ALL':
            products = service_class().save_data_products(observation_record)
            messages.success(request, 'Saved all available data products')
        else:
            for product in products:
                products = service_class().save_data_products(
                    observation_record,
                    product
                )
                messages.success(
                    request,
                    'Successfully saved: {0}'.format('\n'.join(
                        [str(p) for p in products]
                    ))
                )
        return redirect(reverse(
            'tom_observations:detail',
            kwargs={'pk': observation_record.id})
        )


class DataProductUploadView(LoginRequiredMixin, FormView):
    form_class = DataProductUploadForm
    template_name = 'tom_dataproducts/partials/upload_dataproduct.html'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            target = form.cleaned_data['target']
            if not target:
                observation_record = form.cleaned_data['observation_record']
                target = observation_record.target
            else:
                observation_record = None
            tag = form.cleaned_data['tag']
            data_product_files = request.FILES.getlist('files')
            for f in data_product_files:
                dp = DataProduct(
                    target=target,
                    observation_record=observation_record,
                    data=f,
                    product_id=None,
                    tag=tag
                )
                dp.save()
                process_data_product(dp, target)
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        else:
            return super().form_invalid(form)


class DataProductDeleteView(LoginRequiredMixin, DeleteView):
    model = DataProduct
    success_url = reverse_lazy('home')

    def get_success_url(self):
        referer = self.request.GET.get('next', None)
        referer = urlparse(referer).path if referer else '/'
        return referer

    def delete(self, request, *args, **kwargs):
        self.get_object().data.delete()
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['next'] = self.request.META.get('HTTP_REFERER', '/')
        return context


class DataProductListView(FilterView):
    model = DataProduct
    template_name = 'tom_dataproducts/dataproduct_list.html'
    paginate_by = 25
    filterset_fields = ['target__name', 'observation_record__facility']
    strict = False

    def get_queryset(self):
        return super().get_queryset().filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['product_groups'] = DataProductGroup.objects.all()
        return context


class DataProductFeatureView(View):
    def get(self, request, *args, **kwargs):
        product_id = kwargs.get('pk', None)
        product = DataProduct.objects.get(pk=product_id)
        try:
            current_featured = DataProduct.objects.filter(
                featured=True,
                tag=product.tag,
                target=product.target
            )
            for featured_image in current_featured:
                featured_image.featured = False
                featured_image.save()
                featured_image_cache_key = make_template_fragment_key(
                    'featured_image',
                    str(featured_image.target.id)
                )
                cache.delete(featured_image_cache_key)
        except DataProduct.DoesNotExist:
            pass
        product.featured = True
        product.save()
        return redirect(reverse(
            'tom_targets:detail',
            kwargs={'pk': request.GET.get('target_id')})
        )


class DataProductGroupDetailView(DetailView):
    model = DataProductGroup

    def post(self, request, *args, **kwargs):
        group = self.get_object()
        for product in request.POST.getlist('products'):
            group.dataproduct_set.remove(DataProduct.objects.get(pk=product))
        group.save()
        return redirect(reverse(
            'tom_dataproducts:group-detail',
            kwargs={'pk': group.id})
        )


class DataProductGroupListView(ListView):
    model = DataProductGroup


class DataProductGroupCreateView(LoginRequiredMixin, CreateView):
    model = DataProductGroup
    success_url = reverse_lazy('tom_dataproducts:group-list')
    fields = ['name']


class DataProductGroupDeleteView(LoginRequiredMixin, DeleteView):
    success_url = reverse_lazy('tom_dataproducts:group-list')
    model = DataProductGroup


class DataProductGroupDataView(LoginRequiredMixin, FormView):
    form_class = AddProductToGroupForm
    template_name = 'tom_dataproducts/add_product_to_group.html'

    def form_valid(self, form):
        group = form.cleaned_data['group']
        group.dataproduct_set.add(*form.cleaned_data['products'])
        group.save()
        return redirect(reverse(
            'tom_dataproducts:group-detail',
            kwargs={'pk': group.id})
        )


class UpdateReducedDataView(LoginRequiredMixin, RedirectView):
    def get(self, request, *args, **kwargs):
        target_id = request.GET.get('target_id', None)
        out = StringIO()
        if target_id:
            call_command('updatereduceddata', target_id=target_id, stdout=out)
        else:
            call_command('updatereduceddata', stdout=out)
        messages.info(request, out.getvalue())
        return HttpResponseRedirect(self.get_redirect_url(*args, **kwargs))

    def get_redirect_url(self):
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer
