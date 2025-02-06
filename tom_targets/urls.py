from django.urls import path

from .views import TargetCreateView, TargetUpdateView, TargetDetailView, TargetNameSearchView
from .views import TargetDeleteView, TargetListView, TargetImportView, TargetExportView, TargetShareView
from .views import (TargetGroupingView, TargetGroupingDeleteView, TargetGroupingCreateView,
                    TargetAddRemoveGroupingView, TargetMergeView, TargetPersistentShareManageFormView,
                    PersistentShareManageFormView, TargetPersistentShareManageTable, PersistentShareManageTable)
from .views import TargetGroupingShareView, TargetHermesPreloadView, TargetGroupingHermesPreloadView
from .views import TargetSeedView
from .viewsets import PersistentShareViewSet

from .api_views import TargetViewSet, TargetExtraViewSet, TargetNameViewSet, TargetListViewSet
from tom_common.api_router import SharedAPIRootRouter

router = SharedAPIRootRouter()
router.register(r'targets', TargetViewSet, 'targets')
router.register(r'targetextra', TargetExtraViewSet, 'targetextra')
router.register(r'targetname', TargetNameViewSet, 'targetname')
router.register(r'targetlist', TargetListViewSet, 'targetlist')

app_name = 'tom_targets'

urlpatterns = [
    path('', TargetListView.as_view(), name='list'),
    path('targetgrouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('create/', TargetCreateView.as_view(), name='create'),
    path('import/', TargetImportView.as_view(), name='import'),
    path('export/', TargetExportView.as_view(), name='export'),
    path('seed/', TargetSeedView.as_view(), name='seed'),
    path('merge/<int:pk1>/<int:pk2>', TargetMergeView.as_view(), name='merge'),
    path('add-remove-grouping/', TargetAddRemoveGroupingView.as_view(), name='add-remove-grouping'),
    path('name/<str:name>', TargetNameSearchView.as_view(), name='name-search'),
    path('<int:pk>/update/', TargetUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', TargetDeleteView.as_view(), name='delete'),
    path('<int:pk>/share/', TargetShareView.as_view(), name='share'),
    path('<int:pk>/hermes-preload/', TargetHermesPreloadView.as_view(), name='hermes-preload'),
    path('<int:pk>/', TargetDetailView.as_view(), name='detail'),
    path('targetgrouping/<int:pk>/delete/', TargetGroupingDeleteView.as_view(), name='delete-group'),
    path('targetgrouping/create/', TargetGroupingCreateView.as_view(), name='create-group'),
    path('targetgrouping/<int:pk>/share/', TargetGroupingShareView.as_view(), name='share-group'),
    path('targetgrouping/<int:pk>/hermes-preload/', TargetGroupingHermesPreloadView.as_view(),
         name='group-hermes-preload'),
    path('persistentshare/manage/', PersistentShareManageFormView.as_view(), name='persistent-share-manage-form'),
    path('<int:target_pk>/persistentshare/manage/', TargetPersistentShareManageFormView.as_view(),
         name='target-persistent-share-manage-form'),
    path('persistentshare/manage/table', PersistentShareManageTable.as_view(),
         name='persistent-share-manage-table'),
    path('<int:target_pk>/persistentshare/manage/table', TargetPersistentShareManageTable.as_view(),
         name='target-persistent-share-manage-table'),
    path('persistentshare/', PersistentShareViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='persistent-share'),
    path('persistentshare/<int:pk>/',
         PersistentShareViewSet.as_view({'get': 'retrieve', 'delete': 'destroy', 'patch': 'update'}),
         name='persistent-share-detail'),
    path('<int:target_pk>/persistentshare/', PersistentShareViewSet.as_view({'get': 'list'}),
         name='target-persistent-share')
]
