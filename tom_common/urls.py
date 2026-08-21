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
from allauth.account import views as allauth_views
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.views.generic import RedirectView, TemplateView
from django.conf import settings
from django.conf.urls.static import static
from django.apps import apps
from rest_framework.authtoken import views

from tom_base import __version__
from tom_common.api_views import GroupViewSet
from tom_common.views import UserListView, UserPasswordChangeView, UserCreateView, UserDeleteView, UserUpdateView
from tom_common.views import CommentDeleteView, GroupCreateView, GroupUpdateView, GroupDeleteView, UserProfileView
from tom_common.views import RegenerateAPITokenView
from tom_common.views import robots_txt

from .api_router import collect_api_urls, SharedAPIRootRouter  # DRF routers are setup in each INSTALL_APPS url.py

router = SharedAPIRootRouter()
router.register(r'groups', GroupViewSet, 'groups')

urlpatterns = [
    path('', TemplateView.as_view(template_name='tom_common/index.html'),
         kwargs={'version': __version__}, name='home'),
    # django-allauth serves every page under /accounts/ (login, logout, two-factor, password,
    # signup). It is mounted wholesale because allauth internals reverse URL names beyond the
    # obvious ones (account_inactive, account_reauthenticate, account_signup, ...), and it is
    # mounted BEFORE the plugin loop below so that no installed app can shadow the
    # authentication URLs with routes of its own.
    path('accounts/', include('allauth.urls')),
    # Historical URL names: tom_base templates and downstream TOMs reverse 'login' and 'logout',
    # so keep both names working as same-path aliases of the allauth views.
    path('accounts/login/', allauth_views.login, name='login'),
    path('accounts/logout/', allauth_views.logout, name='logout'),
]

# Add the urls from each app that has an include_url_paths method in its AppConfig
for app in apps.get_app_configs():
    try:
        urlpatterns += app.include_url_paths()
    except AttributeError:
        pass

urlpatterns += [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('targets/', include('tom_targets.urls', namespace='targets')),
    path('calendar/', include('tom_calendar.urls', namespace='calendar')),
    path('comments/', include('django_comments.urls')),
    path('observations/', include('tom_observations.urls', namespace='observations')),
    path('dataproducts/', include('tom_dataproducts.urls', namespace='dataproducts')),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/changepassword/', UserPasswordChangeView.as_view(), name='admin-user-change-password'),
    path('users/create/', UserCreateView.as_view(), name='user-create'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user-delete'),
    path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user-update'),
    path('users/<int:pk>/regenerate-token/', RegenerateAPITokenView.as_view(), name='regenerate-api-token'),
    path('users/profile/', UserProfileView.as_view(), name='user-profile'),
    path('groups/create/', GroupCreateView.as_view(), name='group-create'),
    path('groups/<int:pk>/update/', GroupUpdateView.as_view(), name='group-update'),
    path('groups/<int:pk>/delete/', GroupDeleteView.as_view(), name='group-delete'),
    path('comment/<int:pk>/delete', CommentDeleteView.as_view(), name='comment-delete'),
    path('admin/', admin.site.urls),
    # The REST framework's own login page is password-only and would bypass two-factor
    # authentication. The 'rest_framework' namespace must still exist (the browsable API's
    # login/logout links reverse it), so keep the names but send both to the TOM's pages.
    path('api-auth/', include(([
        path('login/', RedirectView.as_view(pattern_name='account_login', query_string=True), name='login'),
        path('logout/', RedirectView.as_view(pattern_name='account_logout', query_string=True), name='logout'),
    ], 'rest_framework'))),
    path('api/', include((collect_api_urls(), 'api'), namespace='api')),
    path('api/token-auth/', views.obtain_auth_token),
    # The static helper below only works in development see
    # https://docs.djangoproject.com/en/2.1/howto/static-files/#serving-files-uploaded-by-a-user-during-development
 ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
