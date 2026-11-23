from django import forms
from django.utils.translation import gettext_lazy as _
from apps.accounting.models import CashTransaction


class CashTransferForm(forms.Form):
    """Deposit drawer cash to bank or withdraw from bank for float."""
    TRANSFER_TYPE_CHOICES = [
        ('BANK_DEPOSIT', _('Deposit Cash into Bank Account (Drawer → Bank)')),
        ('BANK_WITHDRAWAL', _('Withdraw Cash from Bank for Drawer Float (Bank → Drawer)')),
    ]

    transfer_type = forms.ChoiceField(
        choices=TRANSFER_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Transfer Direction')
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
        label=_('Amount (NPR)')
    )
    bank_reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('Bank Deposit Slip # / Cheque #')}),
        label=_('Bank Slip / Cheque Reference')
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
        label=_('Description / Narration')
    )
