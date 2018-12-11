from django.urls import path

from tom_dataproducts.views import DataProductListView, DataProductSaveView, DataProductGroupListView
from tom_dataproducts.views import DataProductDeleteView, DataProductGroupCreateView
from tom_dataproducts.views import DataProductGroupDetailView, GroupDataView, DataProductGroupDeleteView
from tom_dataproducts.views import ManualDataProductUploadView, DataProductFeatureView, DataProductTagView

app_name = 'tom_dataproducts'

urlpatterns = [
    path('data/', DataProductListView.as_view(), name='data-list'),
    path('data/group/create/', DataProductGroupCreateView.as_view(), name='data-group-create'),
    path('data/group/list/', DataProductGroupListView.as_view(), name='data-group-list'),
    path('data/group/add/', GroupDataView.as_view(), name='group-data'),
    path('data/group/<pk>/', DataProductGroupDetailView.as_view(), name='data-group-detail'),
    path('data/group/<pk>/delete/', DataProductGroupDeleteView.as_view(), name='data-group-delete'),
    path('data/upload/', ManualDataProductUploadView.as_view(), name='data-upload'),
    path('data/<pk>/delete/', DataProductDeleteView.as_view(), name='data-delete'),
    path('data/<pk>/feature/', DataProductFeatureView.as_view(), name='data-feature'),
    path('data/<pk>/tag/', DataProductTagView.as_view(), name='data-tag'),
    path('<pk>/save/', DataProductSaveView.as_view(), name='data-save'),
]
