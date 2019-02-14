from django.urls import path

from tom_dataproducts.views import DataProductListView, DataProductSaveView, DataProductGroupListView
from tom_dataproducts.views import DataProductDeleteView, DataProductGroupCreateView
from tom_dataproducts.views import DataProductGroupDetailView, DataProductGroupDataView, DataProductGroupDeleteView
from tom_dataproducts.views import DataProductUploadView, DataProductFeatureView
from tom_dataproducts.views import UpdateReducedDataView

app_name = 'tom_dataproducts'

urlpatterns = [
    path('data/', DataProductListView.as_view(), name='list'),
    path('data/group/create/', DataProductGroupCreateView.as_view(), name='group-create'),
    path('data/group/list/', DataProductGroupListView.as_view(), name='group-list'),
    path('data/group/add/', DataProductGroupDataView.as_view(), name='group-data'),
    path('data/group/<pk>/', DataProductGroupDetailView.as_view(), name='group-detail'),
    path('data/group/<pk>/delete/', DataProductGroupDeleteView.as_view(), name='group-delete'),
    path('data/upload/', DataProductUploadView.as_view(), name='upload'),
    path('data/reduced/update/', UpdateReducedDataView.as_view(), name='update-reduced-data'),
    path('data/<pk>/delete/', DataProductDeleteView.as_view(), name='delete'),
    path('data/<pk>/feature/', DataProductFeatureView.as_view(), name='feature'),
    path('<pk>/save/', DataProductSaveView.as_view(), name='save'),
]
