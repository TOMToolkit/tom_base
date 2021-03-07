from django.urls import path

from tom_observations.views import (AddExistingObservationView, ObservationCreateView, ObservationRecordUpdateView,
                                    ObservationGroupCreateView, ObservationGroupDeleteView, ObservationGroupListView,
                                    ObservationListView, ObservationRecordCancelView, ObservationRecordDetailView,
                                    ObservationTemplateCreateView, ObservationTemplateDeleteView,
                                    ObservationTemplateListView, ObservationTemplateUpdateView)
from tom_observations.api_views import ObservationRecordViewSet
from tom_common.api_router import SharedAPIRootRouter

router = SharedAPIRootRouter()
router.register(r'observations', ObservationRecordViewSet, 'observations')

app_name = 'tom_observations'

urlpatterns = [
    path('add/', AddExistingObservationView.as_view(), name='add-existing'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('template/list/', ObservationTemplateListView.as_view(), name='template-list'),
    path('template/<str:facility>/create/', ObservationTemplateCreateView.as_view(), name='template-create'),
    path('template/<int:pk>/update/', ObservationTemplateUpdateView.as_view(), name='template-update'),
    path('template/<int:pk>/delete/', ObservationTemplateDeleteView.as_view(), name='template-delete'),
    path('template/<int:pk>/', ObservationTemplateUpdateView.as_view(), name='template-detail'),
    # This path must be above <str:facility>/create
    path('groups/create/', ObservationGroupCreateView.as_view(), name='group-create'),
    path('groups/list/', ObservationGroupListView.as_view(), name='group-list'),
    path('groups/<int:pk>/delete/', ObservationGroupDeleteView.as_view(), name='group-delete'),
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('<int:pk>/cancel/', ObservationRecordCancelView.as_view(), name='cancel'),
    path('<int:pk>/update/', ObservationRecordUpdateView.as_view(), name='update'),
    path('<int:pk>/', ObservationRecordDetailView.as_view(), name='detail'),
]
