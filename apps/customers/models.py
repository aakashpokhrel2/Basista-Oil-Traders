from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from common.date_utils import ad_to_bs


class Customer(models.Model):
    """
    Corporate and institutional credit customers (Transporters, Bus Cooperatives, Construction Firms).
    """
    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('BLOCKED', _('Credit Blocked')),
        ('INACTIVE', _('Inactive')),
    ]

    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name=_('Customer / Company Name')
    )
    contact_person = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Contact Person')
    )
    phone = models.CharField(
        max_length=30,
        verbose_name=_('Phone Number')
    )
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('Email')
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Address')
    )
    pan_vat_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_('PAN / VAT Number')
    )
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('50000.00'),
        verbose_name=_('Credit Limit (NPR)'),
        help_text=_('Maximum permissible outstanding credit for fuel purchases')
    )
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Current Outstanding Credit (NPR)'),
        help_text=_('Total unpaid fuel credit amount owed to petrol station')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name=_('Account Status')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Credit Customer')
        verbose_name_plural = _('Credit Customers')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (Credit Owed: NPR {self.current_balance})"

    @property
    def available_credit(self) -> Decimal:
        return max(self.credit_limit - self.current_balance, Decimal('0.00'))

    @property
    def is_credit_exceeded(self) -> bool:
        return self.current_balance > self.credit_limit


class CustomerPayment(models.Model):
    """
    Customer credit repayments / collections.
    Reduces customer outstanding credit balance and posts double-entry cash/bank receipt.
    """
    PAYMENT_METHOD_CHOICES = [
        ('CASH', _('Cash Payment')),
        ('BANK_TRANSFER', _('Bank Transfer (ConnectIPS / RTGS)')),
        ('QR_FONEPAY', _('QR / Fonepay')),
        ('CHEQUE', _('Bank Cheque')),
    ]

    receipt_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name=_('Money Receipt #')
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('Customer')
    )
    payment_date = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Payment Date (AD)')
    )
    payment_date_bs = models.CharField(
        max_length=30,
        verbose_name=_('Payment Date (BS)')
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Amount Received (NPR)')
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name=_('Payment Method')
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Bank Reference / Cheque / Txn ID')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name=_('Collected By')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes / Remarks')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Customer Payment')
        verbose_name_plural = _('Customer Payments')
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"{self.receipt_number} | {self.customer.name} | NPR {self.amount}"

    def clean(self):
        if not self.payment_date_bs and self.payment_date:
            bs_obj = ad_to_bs(self.payment_date)
            if bs_obj:
                self.payment_date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"
        if self.amount is not None and self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': _("Payment amount must be greater than zero.")})
