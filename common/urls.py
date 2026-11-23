from django.urls import path
from common import views

app_name = 'common'

urlpatterns = [
    path('switch-language/', views.switch_language, name='switch_language'),
    path('api/convert-date/', views.convert_date_api, name='convert_date_api'),
]
