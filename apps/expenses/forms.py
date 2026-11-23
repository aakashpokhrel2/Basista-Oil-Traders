from django import forms
from django.utils.translation import gettext_lazy as _
from apps.expenses.models import ExpenseCategory, Expense


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name_en', 'name_ne', 'code', 'description', 'is_active']
        widgets = {
            'name_en': forms.TextInput(attrs={'class': 'form-input'}),
            'name_ne': forms.TextInput(attrs={'class': 'form-input'}),
            'code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'EXP_XXX'}),
            'description': forms.TextInput(attrs={'class': 'form-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'date', 'category', 'amount', 'description', 'payee_name',
            'payment_method', 'reference_number', 'supporting_document'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': _('Details of expenditure...')}),
            'payee_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('Recipient / Vendor')}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('Bill # / Cheque #')}),
            'supporting_document': forms.FileInput(attrs={'class': 'form-input'}),
        }
