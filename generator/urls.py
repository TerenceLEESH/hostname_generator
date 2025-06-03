from django.urls import path
from . import views

urlpatterns = [
    path('', views.esxi_hostname_generator, name='esxi_hostname_generator'),
    path('validate/', views.validate_hostname_ajax, name='validate_hostname'),
]