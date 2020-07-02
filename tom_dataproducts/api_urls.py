from rest_framework.routers import DefaultRouter

from .api_views import DataProductGroupViewSet, DataProductViewSet, ReducedDatumViewSet

"""A url module specifically for api paths, separate from
the rest so it can be included in a modular fashion.
"""

app_name = 'api'

router = DefaultRouter()

# prefix, ViewSet, basename
router.register(r'dataproductgroups', DataProductGroupViewSet)
router.register(r'dataproducts', DataProductViewSet)
router.register(r'reduceddatums', ReducedDatumViewSet)

urlpatterns = router.urls
