from django.urls import path

from tom_observations.views import (AddExistingObservationView, ObservationCreateView, ObservationRecordUpdateView,
                                    ObservationGroupDeleteView, ObservationGroupListView, ObservationListView,
                                    ObservationRecordDetailView, ObservingStrategyCreateView,
                                    ObservingStrategyDeleteView, ObservingStrategyListView,
                                    ObservingStrategyUpdateView)

app_name = 'tom_observations'

urlpatterns = [
    path('add/', AddExistingObservationView.as_view(), name='add-existing'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('strategy/list/', ObservingStrategyListView.as_view(), name='strategy-list'),
    path('strategy/<str:facility>/create/', ObservingStrategyCreateView.as_view(), name='strategy-create'),
    path('strategy/<int:pk>/update/', ObservingStrategyUpdateView.as_view(), name='strategy-update'),
    path('strategy/<int:pk>/delete/', ObservingStrategyDeleteView.as_view(), name='strategy-delete'),
    path('strategy/<int:pk>/', ObservingStrategyUpdateView.as_view(), name='strategy-detail'),
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('<int:pk>/update/', ObservationRecordUpdateView.as_view(), name='update'),
    path('<int:pk>/', ObservationRecordDetailView.as_view(), name='detail'),
    path('groups/list/', ObservationGroupListView.as_view(), name='group-list'),
    path('groups/<int:pk>/delete/', ObservationGroupDeleteView.as_view(), name='group-delete'),
]
