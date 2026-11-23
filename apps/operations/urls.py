from django.urls import path
from apps.operations import views

app_name = 'operations'

urlpatterns = [
    # 1. Shift Management
    path('shifts/', views.ShiftListView.as_view(), name='shift_list'),
    path('shifts/open/', views.shift_open_view, name='shift_open'),
    path('shifts/<int:pk>/', views.shift_detail_view, name='shift_detail'),
    path('shifts/<int:pk>/close/', views.shift_close_view, name='shift_close'),
    path('shifts/<int:pk>/approve/', views.shift_approve_view, name='shift_approve'),

    # 2. Meter Readings
    path('meter-readings/', views.MeterReadingListView.as_view(), name='meter_reading_list'),
    path('meter-readings/add/', views.meter_reading_create_view, name='meter_reading_create'),

    # 3. Fuel Sales Register & Manual Sales
    path('sales/', views.DailySalesRegisterView.as_view(), name='sales_register'),
    path('sales/manual/', views.manual_sale_create_view, name='manual_sale_create'),
    path('sales/<int:pk>/', views.sale_detail_view, name='sale_detail'),
    path('sales/<int:pk>/cancel/', views.sale_cancel_view, name='sale_cancel'),

    # 4. Stock Movement Ledger & Adjustments
    path('stock/', views.StockMovementLedgerView.as_view(), name='stock_ledger'),
    path('stock/adjust/', views.stock_adjustment_create_view, name='stock_adjust'),
    path('stock/adjust/new/', views.stock_adjustment_create_view, name='stock_adjustment_create'),

    # 5. Sales Reconciliation & Reports
    path('reconciliation/', views.sales_reconciliation_view, name='sales_reconciliation'),
]
