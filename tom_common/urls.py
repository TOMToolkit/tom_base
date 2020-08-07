"""tom_base URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static

from tom_common.views import UserListView, UserPasswordChangeView, UserCreateView, UserDeleteView, UserUpdateView
from tom_common.views import CommentDeleteView, GroupCreateView, GroupUpdateView, GroupDeleteView

from rest_framework import routers
from tom_targets.api_views import TargetViewSet, TargetNameViewSet, TargetExtraViewSet
from tom_dataproducts.api_views import DataProductViewSet

# For all applications, set up the DRF router, its router.urls is included in urlpatterns below
router = routers.DefaultRouter()
router.register(r'targets', TargetViewSet, 'targets')
router.register(r'targetextra', TargetExtraViewSet, 'targetextra')
router.register(r'targetname', TargetNameViewSet, 'targetname')
router.register(r'dataproducts', DataProductViewSet, 'dataproducts')


urlpatterns = [
    path('', TemplateView.as_view(template_name='tom_common/index.html'), name='home'),
    path('targets/', include('tom_targets.urls', namespace='targets')),
    path('alerts/', include('tom_alerts.urls', namespace='alerts')),
    path('comments/', include('django_comments.urls')),
    path('catalogs/', include('tom_catalogs.urls')),
    path('observations/', include('tom_observations.urls', namespace='observations')),
    path('dataproducts/', include('tom_dataproducts.urls', namespace='dataproducts')),
    path('publications/', include('tom_publications.urls', namespace='publications')),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/changepassword/', UserPasswordChangeView.as_view(), name='admin-user-change-password'),
    path('users/create/', UserCreateView.as_view(), name='user-create'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user-delete'),
    path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user-update'),
    path('groups/create/', GroupCreateView.as_view(), name='group-create'),
    path('groups/<int:pk>/update/', GroupUpdateView.as_view(), name='group-update'),
    path('groups/<int:pk>/delete/', GroupDeleteView.as_view(), name='group-delete'),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('comment/<int:pk>/delete', CommentDeleteView.as_view(), name='comment-delete'),
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/', include((router.urls, 'api'), namespace='api')),
    # The static helper below only works in development see
    # https://docs.djangoproject.com/en/2.1/howto/static-files/#serving-files-uploaded-by-a-user-during-development
 ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
