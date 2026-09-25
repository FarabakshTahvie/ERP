from django.urls import path
from .views import register_push_device
from . import dev_test_views

app_name = 'utils'

urlpatterns = [
    path('api/register-device/', register_push_device, name='register_push_device'),
    path('dev-test/calendar/', dev_test_views.dev_test_calendar, name='dev_test_calendar'),
    path('dev-test/map/', dev_test_views.dev_test_map, name='dev_test_map'),
    path('dev-test/design-system/', dev_test_views.dev_test_design_system, name='dev_test_design_system'),
]
