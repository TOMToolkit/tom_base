from django.urls import path

from tom_observations.views import ObservationCreateView, ManualObservationCreateView, DataProductListView
from tom_observations.views import ObservationRecordDetailView, ObservationListView, DataProductSaveView
from tom_observations.views import DataProductDeleteView, DataProductGroupCreateView, DataProductGroupListView
from tom_observations.views import DataProductGroupDetailView, GroupDataView, DataProductGroupDeleteView
from tom_observations.views import ManualDataProductUploadView, DataProductFeatureView, DataProductTagView

app_name = 'tom_observations'

urlpatterns = [
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('manual/', ManualObservationCreateView.as_view(), name='manual'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('data/', DataProductListView.as_view(), name='data-list'),
    path('data/group/create/', DataProductGroupCreateView.as_view(), name='data-group-create'),
    path('data/group/list/', DataProductGroupListView.as_view(), name='data-group-list'),
    path('data/group/add/', GroupDataView.as_view(), name='group-data'),
    path('data/group/<pk>/', DataProductGroupDetailView.as_view(), name='data-group-detail'),
    path('data/group/<pk>/delete/', DataProductGroupDeleteView.as_view(), name='data-group-delete'),
    path('data/<pk>/upload/', ManualDataProductUploadView.as_view(), name='data-upload'),
    path('data/<pk>/delete/', DataProductDeleteView.as_view(), name='data-delete'),
    path('data/<pk>/feature/', DataProductFeatureView.as_view(), name='data-feature'),
    path('data/<pk>/tag/', DataProductTagView.as_view(), name='data-tag'),
    path('<pk>/', ObservationRecordDetailView.as_view(), name='detail'),
    path('<pk>/save/', DataProductSaveView.as_view(), name='data-save'),
]
