from django.urls import path
from .views import register_push_device

app_name = 'utils'

urlpatterns = [
    path('api/register-device/', register_push_device, name='register_push_device'),
]
