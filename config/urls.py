"""
URL configuration for petrol_station project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView

urlpatterns = [
    # Built-in i18n switcher endpoint (POST /i18n/setlang/)
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='dashboard:index', permanent=False), name='root'),
    path('auth/', include('apps.authentication.urls', namespace='authentication')),
    path('station/', include('apps.station.urls', namespace='station')),
    path('operations/', include('apps.operations.urls', namespace='operations')),
    path('purchases/', include('apps.purchases.urls', namespace='purchases')),
    path('customers/', include('apps.customers.urls', namespace='customers')),
    path('expenses/', include('apps.expenses.urls', namespace='expenses')),
    path('accounting/', include('apps.accounting.urls', namespace='accounting')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('audit/', include('apps.audit.urls', namespace='audit')),
    path('common/', include('common.urls', namespace='common')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
