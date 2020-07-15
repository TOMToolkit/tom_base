from rest_framework.routers import DefaultRouter

from .api_views import TargetViewSet, TargetNamesViewSet

"""A url module specifically for api paths, seperate from
the rest so it can be included modularly.
"""

app_name = 'api'

router = DefaultRouter()
router.register(r'targets', TargetViewSet, 'targets')
router.register(r'targetnames', TargetNamesViewSet, 'targetnames')

urlpatterns = router.urls
