from django.urls import path

from .views import TargetCreate, TargetUpdate, TargetDetail, TargetDelete, TargetListView, TargetImport

app_name = 'tom_targets'

urlpatterns = [
    path('', TargetListView.as_view(), name='list'),
    path('create/', TargetCreate.as_view(), name='create'),
    path('import/', TargetImport.as_view(), name='import'),
    path('<pk>/update/', TargetUpdate.as_view(), name='update'),
    path('<pk>/delete/', TargetDelete.as_view(), name='delete'),
    path('<pk>/', TargetDetail.as_view(), name='detail')
]
