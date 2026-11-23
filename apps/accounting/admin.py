from django.contrib import admin
from apps.accounting.models import FinancialPeriod, Account, JournalEntry, JournalLine, CashTransaction

class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'name_en', 'name_ne', 'account_type', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['account_number', 'name_en', 'name_ne']

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'date', 'reference_type', 'reference_id', 'is_posted', 'is_reversed']
    list_filter = ['is_posted', 'is_reversed', 'date']
    search_fields = ['entry_number', 'reference_id', 'description']
    inlines = [JournalLineInline]

@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ['voucher_number', 'date', 'transaction_type', 'source_category', 'amount', 'balance_after']
    list_filter = ['transaction_type', 'source_category', 'date']
    search_fields = ['voucher_number', 'description']

@admin.register(FinancialPeriod)
class FinancialPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'fiscal_year_bs', 'start_date_ad', 'end_date_ad', 'is_active', 'is_closed']
