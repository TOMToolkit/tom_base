from django.urls import path

from .views import TargetCreateView, TargetUpdateView, TargetDetailView, TargetNameSearchView
from .views import TargetDeleteView, TargetListView, TargetImportView, TargetExportView
from .views import TargetGroupingView, TargetGroupingDeleteView, TargetGroupingCreateView, TargetAddRemoveGroupingView

from .api_views import TargetViewSet, TargetExtraViewSet, TargetNameViewSet
from tom_common.api_router import SharedAPIRootRouter

router = SharedAPIRootRouter()
router.register(r'targets', TargetViewSet, 'targets')
router.register(r'targetextra', TargetExtraViewSet, 'targetextra')
router.register(r'targetname', TargetNameViewSet, 'targetname')

app_name = 'tom_targets'

urlpatterns = [
    path('', TargetListView.as_view(), name='list'),
    path('targetgrouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('create/', TargetCreateView.as_view(), name='create'),
    path('import/', TargetImportView.as_view(), name='import'),
    path('export/', TargetExportView.as_view(), name='export'),
    path('add-remove-grouping/', TargetAddRemoveGroupingView.as_view(), name='add-remove-grouping'),
    path('name/<str:name>', TargetNameSearchView.as_view(), name='name-search'),
    path('<int:pk>/update/', TargetUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', TargetDeleteView.as_view(), name='delete'),
    path('<int:pk>/', TargetDetailView.as_view(), name='detail'),
    path('targetgrouping/<int:pk>/delete/', TargetGroupingDeleteView.as_view(), name='delete-group'),
    path('targetgrouping/create/', TargetGroupingCreateView.as_view(), name='create-group')
]
