from django.urls import path

from tom_observations.views import (ManualObservationCreateView, ObservationCreateView,
                                    ObservationGroupDeleteView, ObservationGroupListView, ObservationListView,
                                    ObservationRecordDetailView, ObservingStrategyCreateView,
                                    ObservingStrategyDeleteView, ObservingStrategyListView,
                                    ObservingStrategyUpdateView)

app_name = 'tom_observations'

urlpatterns = [
    path('manual/', ManualObservationCreateView.as_view(), name='manual'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('strategy/list/', ObservingStrategyListView.as_view(), name='strategy-list'),
    path('strategy/create/', ObservingStrategyCreateView.as_view(), name='strategy-create'),
    path('strategy/<pk>/update/', ObservingStrategyUpdateView.as_view(), name='strategy-update'),
    path('strategy/<pk>/delete/', ObservingStrategyDeleteView.as_view(), name='strategy-delete'),
    path('strategy/<pk>/', ObservingStrategyUpdateView.as_view(), name='strategy-detail'),
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('<pk>/', ObservationRecordDetailView.as_view(), name='detail'),
    path('groups/list/', ObservationGroupListView.as_view(), name='group-list'),
    path('groups/<int:pk>/delete/', ObservationGroupDeleteView.as_view(), name='group-delete'),
]
