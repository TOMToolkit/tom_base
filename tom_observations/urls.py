from django.urls import path

from tom_observations.views import ObservationCreateView, ManualObservationCreateView, DataProductListView
from tom_observations.views import ObservationRecordDetailView, ObservationListView, DataProductSaveView
from tom_observations.views import DataProductDeleteView

app_name = 'tom_observations'

urlpatterns = [
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('manual/', ManualObservationCreateView.as_view(), name='manual'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('data/', DataProductListView.as_view(), name='data-list'),
    path('data/<pk>/delete/', DataProductDeleteView.as_view(), name='data-delete'),
    path('<pk>/', ObservationRecordDetailView.as_view(), name='detail'),
    path('<pk>/save/', DataProductSaveView.as_view(), name='data-save'),
]
