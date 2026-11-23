from django.urls import path
from apps.purchases import views

app_name = 'purchases'

urlpatterns = [
    # Suppliers
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/new/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<int:supplier_id>/pay/', views.supplier_payment_create_view, name='supplier_payment'),

    # Fuel Purchases
    path('orders/', views.FuelPurchaseListView.as_view(), name='purchase_list'),
    path('orders/new/', views.FuelPurchaseCreateView.as_view(), name='purchase_create'),
    path('orders/<int:pk>/', views.FuelPurchaseDetailView.as_view(), name='purchase_detail'),
    path('orders/<int:pk>/approve/', views.purchase_approve_view, name='purchase_approve'),
]
