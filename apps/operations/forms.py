"""
Forms for Shift Management, Meter Reading Entry, Manual Fuel Sales, and Stock Adjustments.
Includes Tailwind styling and strict business validation.
"""

from decimal import Decimal
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authentication.models import User
from apps.station.models import FuelType, StorageTank, Nozzle, FuelPrice
from apps.station.forms import TailwindWidgetMixin
from apps.operations.models import Shift, ShiftSchedule, MeterReading, FuelSale, StockMovement
from common.date_utils import get_current_bs_date


class ShiftOpenForm(forms.ModelForm, TailwindWidgetMixin):
    """Form to open a new operational shift session."""
    class Meta:
        model = Shift
        fields = [
            'shift_number', 'schedule', 'supervisor',
            'operators', 'opening_cash_balance'
        ]
        widgets = {
            'operators': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()

        # Suggest default sequential shift number
        if not self.initial.get('shift_number') and not self.instance.pk:
            bs_today = get_current_bs_date()
            today_str = bs_today.strftime('%Y%m%d') if bs_today else timezone.now().strftime('%Y%m%d')
            count_today = Shift.objects.filter(date_ad=timezone.now().date()).count() + 1
            self.fields['shift_number'].initial = f"S-{today_str}-{count_today}"

        # Filter staff choices
        self.fields['supervisor'].queryset = User.objects.filter(
            is_active=True, role__in=['OWNER', 'MANAGER', 'ACCOUNTANT']
        )
        self.fields['operators'].queryset = User.objects.filter(
            is_active=True, role__in=['PUMP_OPERATOR', 'CASHIER', 'MANAGER']
        )


class ShiftCloseForm(forms.ModelForm, TailwindWidgetMixin):
    """Form to close active shift with physical cash count and handover notes."""
    class Meta:
        model = Shift
        fields = [
            'closing_cash_balance', 'actual_cash_collected', 'handover_notes'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class MeterReadingForm(forms.ModelForm, TailwindWidgetMixin):
    """Form to log closing meter reading per nozzle."""
    class Meta:
        model = MeterReading
        fields = [
            'nozzle', 'closing_meter_reading', 'test_dispense_quantity',
            'is_rollover', 'rollover_reason', 'notes'
        ]

    def __init__(self, *args, **kwargs):
        self.shift = kwargs.pop('shift', None)
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()

        # Filter nozzles not yet read in this shift
        if self.shift:
            existing_read_nozzles = MeterReading.objects.filter(shift=self.shift).values_list('nozzle_id', flat=True)
            self.fields['nozzle'].queryset = Nozzle.objects.filter(status='ACTIVE').exclude(id__in=existing_read_nozzles)


class ManualSaleForm(forms.ModelForm, TailwindWidgetMixin):
    """Form to record an authorized manual fuel sale."""
    class Meta:
        model = FuelSale
        fields = [
            'fuel_type', 'tank', 'nozzle', 'quantity', 'unit_price',
            'payment_method', 'customer_name', 'vehicle_number', 'reason_for_manual'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()
        self.fields['fuel_type'].queryset = FuelType.objects.filter(is_active=True)
        self.fields['tank'].queryset = StorageTank.objects.filter(is_active=True)
        self.fields['nozzle'].queryset = Nozzle.objects.filter(status='ACTIVE')
        self.fields['nozzle'].required = False

    def clean(self):
        cleaned_data = super().clean()
        fuel_type = cleaned_data.get('fuel_type')
        tank = cleaned_data.get('tank')
        reason = cleaned_data.get('reason_for_manual')

        if not reason or not reason.strip():
            self.add_error('reason_for_manual', _("Reason is mandatory for manual fuel sales entries."))

        if tank and fuel_type and tank.fuel_type != fuel_type:
            self.add_error('tank', _("Selected tank '%(tank)s' contains %(tank_fuel)s, not %(sale_fuel)s.") % {
                'tank': tank.tank_name,
                'tank_fuel': tank.fuel_type.name_en,
                'sale_fuel': fuel_type.name_en
            })

        return cleaned_data


class SaleCancellationForm(forms.Form, TailwindWidgetMixin):
    """Form to void/cancel an erroneous sales transaction."""
    cancellation_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        label=_('Reason for Voiding / Cancellation'),
        help_text=_('State the justification for reversing this sales invoice and returning fuel to inventory.')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class StockAdjustmentForm(forms.ModelForm, TailwindWidgetMixin):
    """Form for authorized dip losses, evaporation, or testing adjustments."""
    class Meta:
        model = StockMovement
        fields = ['tank', 'movement_type', 'quantity', 'remarks']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()
        self.fields['tank'].queryset = StorageTank.objects.filter(is_active=True)
        self.fields['movement_type'].choices = [
            ('ADJUSTMENT_LOSS', _('Evaporation / Dip Loss (-)')),
            ('ADJUSTMENT_GAIN', _('Calibration / Dip Gain (+)')),
            ('TEST_RETURN', _('Test Measure Can Return (+)')),
        ]
