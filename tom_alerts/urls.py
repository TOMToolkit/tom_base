from django.urls import path

from tom_alerts.views import BrokerQueryCreateView, BrokerQueryListView, BrokerQueryUpdateView, RunQueryView

app_name = 'tom_alerts'

urlpatterns = [
    path('query/list/', BrokerQueryListView.as_view(), name='list'),
    path('query/create/', BrokerQueryCreateView.as_view(), name='create'),
    path('query/<int:id>/update/', BrokerQueryUpdateView.as_view(), name='update'),
    path('query/<int:pk>/run/', RunQueryView.as_view(), name='run')
]
