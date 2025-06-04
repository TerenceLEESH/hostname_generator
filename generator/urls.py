from django.urls import path
from . import views

urlpatterns = [
    path('', views.esxi_hostname_generator, name='esxi_hostname_generator'),
    path('validate/', views.validate_hostname_ajax, name='validate_hostname'),
    path('check-existing-hostnames/', views.check_existing_hostnames, name='check_existing_hostnames'),
    path('generate-sequential/', views.generate_sequential_hostname, name='generate_sequential_hostname'),
]