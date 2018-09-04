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

from tom_common.views import UserListView, UserPasswordChangeView, UserCreateView, UserDeleteView

urlpatterns = [
    path('', TemplateView.as_view(template_name='tom_common/index.html'), name='home'),
    path('targets/', include('tom_targets.urls', namespace='targets')),
    path('alerts/', include('tom_alerts.urls', namespace='alerts')),
    path('comments/', include('django_comments.urls')),
    path('catalogs/', include('tom_catalogs.urls')),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/changepassword/', UserPasswordChangeView.as_view(), name='admin-user-change-password'),
    path('users/create/', UserCreateView.as_view(), name='user-create'),
    path('users/<int:pk>/delete', UserDeleteView.as_view(), name='user-delete'),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
]
