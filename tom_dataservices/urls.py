from django.urls import path

from tom_dataservices.views import DataServiceQueryListView, DataServiceQueryCreateView, RunQueryView
from tom_dataservices.views import DataServiceQueryUpdateView, DataServiceQueryDeleteView, CreateTargetFromQueryView

app_name = 'tom_dataservices'

urlpatterns = [
    path('query/list/', DataServiceQueryListView.as_view(), name='query_list'),
    path('query/create/', DataServiceQueryCreateView.as_view(), name='create'),
    path('query/<int:pk>/update/', DataServiceQueryUpdateView.as_view(), name='update'),
    path('query/<int:pk>/run/', RunQueryView.as_view(), name='run_saved'),
    path('query/run/', RunQueryView.as_view(), name='run'),
    path('query/<int:pk>/delete/', DataServiceQueryDeleteView.as_view(), name='delete'),
    path('query/create_targets/', CreateTargetFromQueryView.as_view(), name='create-target'),
    # path('<str:broker>/submit/', SubmitAlertUpstreamView.as_view(), name='submit-alert')
]
