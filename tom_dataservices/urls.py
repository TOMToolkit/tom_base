from django.urls import path

from tom_dataservices.views import DataServiceQueryListView, DataServiceQueryCreateView

app_name = 'tom_dataservices'

urlpatterns = [
    path('query/list/', DataServiceQueryListView.as_view(), name='query_list'),
    path('query/create/', DataServiceQueryCreateView.as_view(), name='create'),
    # path('query/<int:pk>/update/', BrokerQueryUpdateView.as_view(), name='update'),
    # path('query/<int:pk>/run/', RunQueryView.as_view(), name='run'),
    # path('query/<int:pk>/delete/', BrokerQueryDeleteView.as_view(), name='delete'),
    # path('alert/create/', CreateTargetFromAlertView.as_view(), name='create-target'),
    # path('<str:broker>/submit/', SubmitAlertUpstreamView.as_view(), name='submit-alert')
]
