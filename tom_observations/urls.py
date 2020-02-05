from django.urls import path

from tom_observations.views import (ManualObservationCreateView, ObservationGroupCancelView, ObservationCreateView,
                                    ObservationGroupDeleteView, ObservationGroupListView, ObservationListView,
                                    ObservationRecordDetailView, ObservationStrategyCreateView,
                                    ObservationStrategyListView, ObservationStrategyUpdateView)

app_name = 'tom_observations'

urlpatterns = [
    path('manual/', ManualObservationCreateView.as_view(), name='manual'),
    path('list/', ObservationListView.as_view(), name='list'),
    path('strategy/list/', ObservationStrategyListView.as_view(), name='strategy-list'),
    path('strategy/create/', ObservationStrategyCreateView.as_view(), name='strategy-create'),
    path('strategy/<pk>/', ObservationStrategyUpdateView.as_view(), name='strategy-detail'),
    # path('<pk>/cancel/', ObservationGroupCancelView.as_view(), name='cancel'),
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('<pk>/', ObservationRecordDetailView.as_view(), name='detail'),
    path('groups/list/', ObservationGroupListView.as_view(), name='group-list'),
    path('groups/<int:pk>/delete/', ObservationGroupDeleteView.as_view(), name='group-delete'),
]
