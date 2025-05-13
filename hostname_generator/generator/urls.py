from django.urls import path
from . import views

app_name = 'generator'

urlpatterns = [
    path('', views.index, name='index'),
    path('generate/', views.generate_hostname, name='generate_hostname'),
    path('check_hostname/', views.check_hostname, name='check_hostname'),
]