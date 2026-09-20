"""
URL configuration for FaraBakhsh project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from utils.views import home_view, manifest_view, najva_service_worker

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manifest.json', manifest_view, name='manifest'),
    path('najva-messaging-sw.js', najva_service_worker, name='najva_sw'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('utils/', include('utils.urls', namespace='utils')),
    path('', include('notifications.urls', namespace='notifications')),
    path('', include('projects.urls', namespace='projects')),
    path('', include('finance.urls', namespace='finance')),
    path('', home_view, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
