"""
URL configuration for FaraBakhsh project.
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from utils.views import home_view, manifest_view, najva_service_worker
from utils.media_views import protected_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manifest.json', manifest_view, name='manifest'),
    path('najva-messaging-sw.js', najva_service_worker, name='najva_sw'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('manager/', include('dashboard.urls', namespace='dashboard')),
    path('people/', include('people.urls', namespace='people')),
    path('tasks/', include('tasks.urls', namespace='tasks')),
    path('messenger/', include('messenger.urls', namespace='messenger')),
    path('utils/', include('utils.urls', namespace='utils')),
    path('', include('inventory.urls', namespace='inventory')),
    path('', include('notifications.urls', namespace='notifications')),
    path('', include('projects.urls', namespace='projects')),
    path('', include('finance.urls', namespace='finance')),
    re_path(r'^media/(?P<path>.+)$', protected_media, name='protected_media'),
    path('', home_view, name='home'),
]
