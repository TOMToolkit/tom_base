from django.urls import path

from .views import TargetCreateView, TargetUpdateView, TargetDetailView
from .views import TargetDeleteView, TargetListView, TargetImportView, TargetExportAllView, TargetExportFilteredView

app_name = 'tom_targets'

urlpatterns = [
    path('', TargetListView.as_view(), name='list'),
    path('create/', TargetCreateView.as_view(), name='create'),
    path('import/', TargetImportView.as_view(), name='import'),
    path('export/all/', TargetExportAllView.as_view(), name='export-all'),
    path('export/filtered/', TargetExportFilteredView.as_view(), name='export-filtered'),
    path('<pk>/update/', TargetUpdateView.as_view(), name='update'),
    path('<pk>/delete/', TargetDeleteView.as_view(), name='delete'),
    path('<pk>/', TargetDetailView.as_view(), name='detail')
]
