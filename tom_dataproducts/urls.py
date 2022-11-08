from django.urls import path

from tom_dataproducts.views import DataProductListView, DataProductSaveView, DataProductGroupListView
from tom_dataproducts.views import DataProductDeleteView, DataProductGroupCreateView
from tom_dataproducts.views import DataProductGroupDetailView, DataProductGroupDataView, DataProductGroupDeleteView
from tom_dataproducts.views import DataProductUploadView, DataProductFeatureView, UpdateReducedDataView
from tom_dataproducts.views import DataShareView

from tom_common.api_router import SharedAPIRootRouter
from tom_dataproducts.api_views import DataProductViewSet

router = SharedAPIRootRouter()
router.register(r'dataproducts', DataProductViewSet, 'dataproducts')

app_name = 'tom_dataproducts'

urlpatterns = [
    path('data/', DataProductListView.as_view(), name='list'),
    path('data/group/create/', DataProductGroupCreateView.as_view(), name='group-create'),
    path('data/group/list/', DataProductGroupListView.as_view(), name='group-list'),
    path('data/group/add/', DataProductGroupDataView.as_view(), name='group-data'),
    path('data/group/<int:pk>/', DataProductGroupDetailView.as_view(), name='group-detail'),
    path('data/group/<int:pk>/delete/', DataProductGroupDeleteView.as_view(), name='group-delete'),
    path('data/upload/', DataProductUploadView.as_view(), name='upload'),
    path('data/reduced/update/', UpdateReducedDataView.as_view(), name='update-reduced-data'),
    path('data/<int:pk>/delete/', DataProductDeleteView.as_view(), name='delete'),
    path('data/<int:pk>/feature/', DataProductFeatureView.as_view(), name='feature'),
    path('data/<int:dp_pk>/share/', DataShareView.as_view(), name='share'),
    path('target/<int:tg_pk>/share/', DataShareView.as_view(), name='share_all'),
    path('<int:pk>/save/', DataProductSaveView.as_view(), name='save'),
]
