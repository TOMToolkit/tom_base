from django.urls import path

from .views import TargetCreateView, TargetUpdateView, TargetDetailView
from .views import TargetDeleteView, TargetListView, TargetImportView, TargetGroupingView, TargetAddRemoveGroupingView

app_name = 'tom_targets'

urlpatterns = [
    path('', TargetListView.as_view(), name='list'),
    path('targetgrouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('create/', TargetCreateView.as_view(), name='create'),
    path('import/', TargetImportView.as_view(), name='import'),
    path('add-remove-grouping/', TargetAddRemoveGroupingView.as_view(), name='add-remove-grouping'),
    path('<pk>/update/', TargetUpdateView.as_view(), name='update'),
    path('<pk>/delete/', TargetDeleteView.as_view(), name='delete'),
    path('<pk>/', TargetDetailView.as_view(), name='detail'),
]
