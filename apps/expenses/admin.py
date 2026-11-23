from django.contrib import admin
from apps.expenses.models import ExpenseCategory, Expense

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name_en', 'name_ne', 'code', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name_en', 'name_ne', 'code']

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['voucher_number', 'date', 'category', 'amount', 'payment_method', 'approval_status']
    list_filter = ['category', 'payment_method', 'approval_status', 'date']
    search_fields = ['voucher_number', 'payee_name', 'description']
