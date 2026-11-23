"""
Bilingual forms for Station Configuration, Fuel Types, Storage Tanks, Pumps, Nozzles, and Pricing.
Includes Tailwind styling and strict operational validation rules.
"""

from decimal import Decimal
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.station.models import (
    StationConfiguration,
    FuelType,
    StorageTank,
    Pump,
    Nozzle,
    FuelPrice,
)


class TailwindWidgetMixin:
    """Applies clean Tailwind CSS classes to form widgets."""
    def apply_tailwind_classes(self):
        for field_name, field in self.fields.items():
            widget = field.widget
            widget_type = widget.__class__.__name__

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({
                    'class': 'h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500'
                })
            elif isinstance(widget, forms.Select):
                widget.attrs.update({
                    'class': 'w-full rounded-lg border border-gray-300 bg-white px-3.5 py-2.5 text-sm text-gray-900 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20'
                })
            elif isinstance(widget, forms.FileInput):
                widget.attrs.update({
                    'class': 'w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100'
                })
            elif isinstance(widget, forms.Textarea):
                widget.attrs.update({
                    'class': 'w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20',
                    'rows': 3,
                })
            else:
                existing_class = widget.attrs.get('class', '')
                widget.attrs.update({
                    'class': f'{existing_class} w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20'
                })


class StationConfigurationForm(forms.ModelForm, TailwindWidgetMixin):
    """Station business settings and IRD PAN/VAT details."""
    class Meta:
        model = StationConfiguration
        fields = [
            'station_name_en', 'station_name_ne',
            'station_address_en', 'station_address_ne',
            'phone_number', 'email', 'pan_vat_number',
            'currency', 'timezone', 'default_language', 'financial_year', 'logo'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class FuelTypeForm(forms.ModelForm, TailwindWidgetMixin):
    """Fuel product configuration (Petrol, Diesel)."""
    class Meta:
        model = FuelType
        fields = [
            'name_en', 'name_ne', 'code', 'unit',
            'color_code', 'badge_class', 'display_order', 'is_active'
        ]
        widgets = {
            'color_code': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-20 p-1 border rounded-md'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class StorageTankForm(forms.ModelForm, TailwindWidgetMixin):
    """Underground fuel storage tank management."""
    class Meta:
        model = StorageTank
        fields = [
            'tank_number', 'tank_name', 'fuel_type',
            'capacity_liters', 'opening_stock', 'current_stock',
            'alert_threshold', 'installation_date', 'is_active'
        ]
        widgets = {
            'installation_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()

    def clean(self):
        cleaned_data = super().clean()
        capacity = cleaned_data.get('capacity_liters')
        opening_stock = cleaned_data.get('opening_stock')
        current_stock = cleaned_data.get('current_stock')

        if capacity is not None and capacity <= 0:
            self.add_error('capacity_liters', _('Tank capacity must be greater than zero.'))

        if capacity is not None:
            if opening_stock is not None and opening_stock > capacity:
                self.add_error('opening_stock', _('Opening stock cannot exceed maximum tank capacity (%(cap)s L).') % {'cap': capacity})
            if current_stock is not None and current_stock > capacity:
                self.add_error('current_stock', _('Current stock cannot exceed maximum tank capacity (%(cap)s L).') % {'cap': capacity})

        return cleaned_data


class PumpForm(forms.ModelForm, TailwindWidgetMixin):
    """Dispensing pump configuration."""
    class Meta:
        model = Pump
        fields = [
            'pump_number', 'pump_name', 'serial_number',
            'model_name', 'status', 'installation_date', 'notes'
        ]
        widgets = {
            'installation_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class NozzleForm(forms.ModelForm, TailwindWidgetMixin):
    """Nozzle configuration with fuel compatibility validation."""
    class Meta:
        model = Nozzle
        fields = [
            'pump', 'nozzle_number', 'nozzle_code',
            'fuel_type', 'tank', 'current_meter_reading',
            'status', 'installation_date'
        ]
        widgets = {
            'installation_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()
        # Filter tanks to active tanks
        self.fields['tank'].queryset = StorageTank.objects.filter(is_active=True)
        self.fields['fuel_type'].queryset = FuelType.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        pump = cleaned_data.get('pump')
        nozzle_number = cleaned_data.get('nozzle_number')
        fuel_type = cleaned_data.get('fuel_type')
        tank = cleaned_data.get('tank')
        nozzle_code = cleaned_data.get('nozzle_code')

        # Auto-generate nozzle code if blank
        if pump and nozzle_number and not nozzle_code:
            cleaned_data['nozzle_code'] = f"P{pump.pump_number}-N{nozzle_number}"

        # Fuel type compatibility check:
        if tank and fuel_type and tank.fuel_type != fuel_type:
            msg = _("Incompatible fuel assignment! Tank '%(tank)s' contains %(tank_fuel)s, but nozzle is configured for %(nozzle_fuel)s.") % {
                'tank': tank.tank_name,
                'tank_fuel': tank.fuel_type.name_en,
                'nozzle_fuel': fuel_type.name_en
            }
            self.add_error('tank', msg)

        return cleaned_data


class FuelPriceForm(forms.ModelForm, TailwindWidgetMixin):
    """Fuel price revision form."""
    class Meta:
        model = FuelPrice
        fields = [
            'fuel_type', 'purchase_price', 'selling_price',
            'effective_date', 'approval_status', 'notes'
        ]
        widgets = {
            'effective_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()
        self.fields['fuel_type'].queryset = FuelType.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        purchase_price = cleaned_data.get('purchase_price')
        selling_price = cleaned_data.get('selling_price')

        if purchase_price and purchase_price <= 0:
            self.add_error('purchase_price', _('Purchase price must be positive.'))
        if selling_price and selling_price <= 0:
            self.add_error('selling_price', _('Selling price must be positive.'))

        if purchase_price and selling_price and selling_price < purchase_price:
            self.add_error('selling_price', _('Selling price cannot be less than purchase price.'))

        return cleaned_data
