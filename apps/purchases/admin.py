from django.contrib import admin
from apps.purchases.models import Supplier, FuelPurchase, SupplierPayment

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'contact_person', 'current_balance', 'status']
    list_filter = ['status']
    search_fields = ['name', 'phone', 'pan_vat_number']

@admin.register(FuelPurchase)
class FuelPurchaseAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'supplier', 'fuel_type', 'delivered_quantity', 'total_amount', 'approval_status', 'payment_status']
    list_filter = ['approval_status', 'payment_status', 'fuel_type', 'purchase_date']
    search_fields = ['invoice_number', 'tanker_number', 'supplier__name']

@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_number', 'supplier', 'payment_date', 'amount', 'payment_method']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['payment_number', 'supplier__name', 'payment_reference']
