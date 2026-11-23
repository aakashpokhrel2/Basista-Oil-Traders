from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from apps.operations.models import (
    ShiftSchedule,
    Shift,
    MeterReading,
    FuelSale,
    StockMovement,
)


@admin.register(ShiftSchedule)
class ShiftScheduleAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'name_ne', 'start_time', 'end_time', 'is_active')
    list_filter = ('is_active',)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('shift_number', 'schedule', 'date_ad', 'date_bs', 'supervisor', 'status', 'opening_cash_balance', 'closing_cash_balance', 'cash_difference')
    list_filter = ('status', 'date_ad', 'schedule')
    search_fields = ('shift_number', 'supervisor__username', 'date_bs')
    filter_horizontal = ('operators',)


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('nozzle', 'shift', 'opening_meter_reading', 'closing_meter_reading', 'quantity_sold', 'net_quantity_sold', 'unit_price', 'total_amount', 'reading_timestamp')
    list_filter = ('nozzle__fuel_type', 'is_rollover', 'reading_timestamp')
    search_fields = ('nozzle__nozzle_code', 'shift__shift_number')


@admin.register(FuelSale)
class FuelSaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'shift', 'sale_type', 'fuel_type', 'quantity', 'unit_price', 'total_amount', 'payment_method', 'customer_name', 'is_cancelled')
    list_filter = ('fuel_type', 'sale_type', 'payment_method', 'is_cancelled', 'transaction_date')
    search_fields = ('invoice_number', 'customer_name', 'vehicle_number')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('tank', 'movement_type', 'direction', 'quantity', 'opening_balance', 'closing_balance', 'reference_id', 'timestamp', 'performed_by')
    list_filter = ('movement_type', 'direction', 'tank', 'timestamp')
    search_fields = ('reference_id', 'tank__tank_number', 'remarks')
