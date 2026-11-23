from django import forms
from django.utils.translation import gettext_lazy as _
from apps.customers.models import Customer, CustomerPayment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'contact_person', 'phone', 'email', 'address',
            'pan_vat_number', 'credit_limit', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('e.g. Bagmati Bus Sewa, Everest Construction')}),
            'contact_person': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '98XXXXXXXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'address': forms.TextInput(attrs={'class': 'form-input'}),
            'pan_vat_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '9-digit PAN/VAT'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class CustomerPaymentForm(forms.ModelForm):
    class Meta:
        model = CustomerPayment
        fields = ['amount', 'payment_method', 'reference_number', 'payment_date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('Bank Cheque # / Fonepay Txn ID')}),
            'payment_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        }
