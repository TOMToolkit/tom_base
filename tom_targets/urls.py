from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import TargetCreateView, TargetUpdateView, TargetDetailView
from .views import TargetDeleteView, TargetListView, TargetImportView, TargetExportView
from .views import TargetGroupingView, TargetGroupingDeleteView, TargetGroupingCreateView, TargetAddRemoveGroupingView
from .api_views import TargetViewSet

app_name = 'tom_targets'

urlpatterns = [
    path('', TargetListView.as_view(), name='list'),
    path('targetgrouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('create/', TargetCreateView.as_view(), name='create'),
    path('import/', TargetImportView.as_view(), name='import'),
    path('export/', TargetExportView.as_view(), name='export'),
    path('add-remove-grouping/', TargetAddRemoveGroupingView.as_view(), name='add-remove-grouping'),
    path('<pk>/update/', TargetUpdateView.as_view(), name='update'),
    path('<pk>/delete/', TargetDeleteView.as_view(), name='delete'),
    path('<pk>/', TargetDetailView.as_view(), name='detail'),
    path('targetgrouping/<int:pk>/delete/', TargetGroupingDeleteView.as_view(), name='delete-group'),
    path('targetgrouping/create/', TargetGroupingCreateView.as_view(), name='create-group')
]

router = DefaultRouter()
router.register(r'targets', TargetViewSet, 'targets')
apiurlpatterns = router.urls
