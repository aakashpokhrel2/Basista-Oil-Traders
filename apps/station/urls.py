from django.urls import path
from apps.station import views

app_name = 'station'

urlpatterns = [
    # 1. Station settings
    path('settings/', views.station_settings_view, name='settings'),

    # 2. Fuel Products
    path('fuels/', views.FuelTypeListView.as_view(), name='fuel_list'),
    path('fuels/add/', views.FuelTypeCreateView.as_view(), name='fuel_create'),
    path('fuels/<int:pk>/edit/', views.FuelTypeUpdateView.as_view(), name='fuel_edit'),
    path('fuels/<int:pk>/toggle/', views.fuel_type_toggle_view, name='fuel_toggle'),

    # 3. Storage Tanks
    path('tanks/', views.StorageTankListView.as_view(), name='tank_list'),
    path('tanks/add/', views.StorageTankCreateView.as_view(), name='tank_create'),
    path('tanks/<int:pk>/edit/', views.StorageTankUpdateView.as_view(), name='tank_edit'),

    # 4. Dispensing Pumps & Nozzles
    path('pumps/', views.PumpListView.as_view(), name='pump_list'),
    path('pumps/add/', views.PumpCreateView.as_view(), name='pump_create'),
    path('pumps/<int:pk>/edit/', views.PumpUpdateView.as_view(), name='pump_edit'),
    path('nozzles/add/', views.NozzleCreateView.as_view(), name='nozzle_create'),
    path('nozzles/<int:pk>/edit/', views.NozzleUpdateView.as_view(), name='nozzle_edit'),

    # 5. Fuel Prices
    path('prices/', views.FuelPriceListView.as_view(), name='price_list'),
    path('prices/add/', views.FuelPriceCreateView.as_view(), name='price_create'),
    path('prices/<int:pk>/approve/', views.fuel_price_approve_view, name='price_approve'),
]
