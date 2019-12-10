from django.urls import path

from tom_observations.views import ObservationCreateView, ManualObservationCreateView
from tom_observations.views import ObservationRecordDetailView, ObservationListView
from tom_observations.views import ObservationGroupListView, ObservationGroupCreateView

app_name = 'tom_observations'

urlpatterns = [
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('manual/', ManualObservationCreateView.as_view(), name='manual'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('<pk>/', ObservationRecordDetailView.as_view(), name='detail'),
    path('groups/list/', ObservationGroupListView.as_view(), name='group-list'),
    path('groups/create/', ObservationCreateView.as_view(), name='group-create')
]
