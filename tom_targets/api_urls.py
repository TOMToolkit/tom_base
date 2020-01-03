from rest_framework.routers import DefaultRouter

from .api_views import TargetViewSet

router = DefaultRouter()
router.register(r'targets', TargetViewSet, 'targets')

urlpatterns = router.urls
