from django.urls import path

from . import views

app_name = 'tom_async_demo'

urlpatterns = [
    path('', views.question_meaning_of_life, name='index'),
    path('start/', views.start_meaning_of_life, name='start'),
    path('answer/<str:result_id>/', views.get_meaning_of_life, name='answer')
]
