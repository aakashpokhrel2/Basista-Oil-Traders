from django import forms
from django.utils.translation import gettext_lazy as _
from apps.purchases.models import Supplier, FuelPurchase, SupplierPayment
from apps.station.models import FuelType, StorageTank


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'name', 'contact_person', 'phone', 'email', 'address',
            'pan_vat_number', 'opening_payable_balance', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('e.g. Nepal Oil Corporation, Amlekhgunj')}),
            'contact_person': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '051-XXXXXX / 98XXXXXXXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'address': forms.TextInput(attrs={'class': 'form-input'}),
            'pan_vat_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '9-digit PAN/VAT'}),
            'opening_payable_balance': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class FuelPurchaseForm(forms.ModelForm):
    class Meta:
        model = FuelPurchase
        fields = [
            'supplier', 'invoice_number', 'purchase_date', 'fuel_type',
            'receiving_tank', 'delivered_quantity', 'purchase_price',
            'tax_amount', 'tanker_number', 'driver_name',
            'chamber_dip_before', 'chamber_dip_after', 'remarks'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('NOC Invoice / Challan #')}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'fuel_type': forms.Select(attrs={'class': 'form-select'}),
            'receiving_tank': forms.Select(attrs={'class': 'form-select'}),
            'delivered_quantity': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': _('Quantity in Litres')}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': _('Rate per Litre')}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'tanker_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Na 7 Kha 4521'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-input'}),
            'chamber_dip_before': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'chamber_dip_after': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fuel_type'].queryset = FuelType.objects.filter(is_active=True)
        self.fields['receiving_tank'].queryset = StorageTank.objects.filter(is_active=True)


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ['amount', 'payment_method', 'payment_reference', 'payment_date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_reference': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('Cheque # / Bank Ref / Txn ID')}),
            'payment_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        }
