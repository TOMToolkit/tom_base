from rest_framework.routers import DefaultRouter

from .api_views import TargetViewSet


app_name = 'api'

router = DefaultRouter()
router.register(r'targets', TargetViewSet, 'targets')

urlpatterns = router.urls
