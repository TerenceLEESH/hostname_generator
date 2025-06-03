from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include all URLs from the generator app
    path('', include('generator.urls')),
]