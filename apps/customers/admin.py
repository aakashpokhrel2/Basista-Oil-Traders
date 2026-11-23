from django.contrib import admin
from apps.customers.models import Customer, CustomerPayment

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'credit_limit', 'current_balance', 'status']
    list_filter = ['status']
    search_fields = ['name', 'phone', 'pan_vat_number']

@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'customer', 'payment_date', 'amount', 'payment_method']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['receipt_number', 'customer__name', 'reference_number']
