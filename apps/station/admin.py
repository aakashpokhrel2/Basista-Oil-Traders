from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from apps.station.models import (
    StationConfiguration,
    FuelType,
    StorageTank,
    Pump,
    Nozzle,
    FuelPrice,
)


@admin.register(StationConfiguration)
class StationConfigurationAdmin(admin.ModelAdmin):
    list_display = ('station_name_en', 'station_name_ne', 'phone_number', 'pan_vat_number', 'financial_year', 'updated_at')

    def has_add_permission(self, request):
        # Enforce singleton
        return not StationConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FuelType)
class FuelTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_en', 'name_ne', 'unit', 'color_code', 'is_active', 'display_order')
    list_editable = ('is_active', 'display_order')
    search_fields = ('name_en', 'name_ne', 'code')


@admin.register(StorageTank)
class StorageTankAdmin(admin.ModelAdmin):
    list_display = ('tank_number', 'tank_name', 'fuel_type', 'capacity_liters', 'current_stock', 'stock_percentage_display', 'is_active')
    list_filter = ('fuel_type', 'is_active')
    search_fields = ('tank_number', 'tank_name')

    def stock_percentage_display(self, obj):
        return f"{obj.stock_percentage}%"
    stock_percentage_display.short_description = _('Fill Level')


class NozzleInline(admin.TabularInline):
    model = Nozzle
    extra = 1
    fields = ('nozzle_number', 'nozzle_code', 'fuel_type', 'tank', 'current_meter_reading', 'status')


@admin.register(Pump)
class PumpAdmin(admin.ModelAdmin):
    list_display = ('pump_number', 'pump_name', 'model_name', 'status', 'nozzles_count', 'installation_date')
    list_filter = ('status',)
    search_fields = ('pump_name', 'serial_number', 'model_name')
    inlines = [NozzleInline]


@admin.register(Nozzle)
class NozzleAdmin(admin.ModelAdmin):
    list_display = ('nozzle_code', 'pump', 'nozzle_number', 'fuel_type', 'tank', 'current_meter_reading', 'status')
    list_filter = ('fuel_type', 'status', 'pump')
    search_fields = ('nozzle_code',)


@admin.register(FuelPrice)
class FuelPriceAdmin(admin.ModelAdmin):
    list_display = ('fuel_type', 'selling_price', 'purchase_price', 'margin_display', 'effective_date', 'approval_status', 'created_by')
    list_filter = ('fuel_type', 'approval_status', 'effective_date')
    search_fields = ('notes', 'fuel_type__name_en')
    date_hierarchy = 'effective_date'

    def margin_display(self, obj):
        return f"NPR {obj.margin_per_liter:.2f}"
    margin_display.short_description = _('Margin/L')
