from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from common.date_utils import ad_to_bs


class ExpenseCategory(models.Model):
    """
    Operational expense classification categories:
    Electricity, Salaries, Rent, Repairs, Transportation, Office, Maintenance, Generator Fuel.
    """
    name_en = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Category Name (EN)')
    )
    name_ne = models.CharField(
        max_length=100,
        verbose_name=_('Category Name (NE)')
    )
    code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name=_('Category Code'),
        help_text=_('e.g. EXP_ELEC, EXP_SAL, EXP_RENT, EXP_REPAIR')
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Description')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active Status')
    )

    class Meta:
        verbose_name = _('Expense Category')
        verbose_name_plural = _('Expense Categories')
        ordering = ['name_en']

    def __str__(self):
        return f"{self.name_en} ({self.name_ne})"


class Expense(models.Model):
    """
    Daily operational expense voucher.
    Supports Cash, Bank, Cheque payments, bill image attachment, and managerial approval.
    """
    PAYMENT_METHOD_CHOICES = [
        ('CASH', _('Cash Payment')),
        ('BANK_TRANSFER', _('Bank Transfer')),
        ('CHEQUE', _('Bank Cheque')),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('APPROVED', _('Approved')),
        ('PENDING', _('Pending Approval')),
        ('REJECTED', _('Rejected')),
    ]

    voucher_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name=_('Expense Voucher #')
    )
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Expense Date (AD)')
    )
    date_bs = models.CharField(
        max_length=30,
        verbose_name=_('Expense Date (BS)')
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='expenses',
        verbose_name=_('Expense Category')
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Amount (NPR)')
    )
    description = models.TextField(
        verbose_name=_('Description / Purpose of Expense')
    )
    payee_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Paid To / Vendor Name'),
        help_text=_('e.g. Nepal Electricity Authority, Landlord, Technician')
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='CASH',
        verbose_name=_('Payment Method')
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Bill # / Cheque # / Reference ID')
    )
    supporting_document = models.FileField(
        upload_to='expenses/%Y/%m/',
        null=True,
        blank=True,
        verbose_name=_('Supporting Bill / Receipt Document')
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='APPROVED',
        verbose_name=_('Approval Status')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expenses_recorded',
        verbose_name=_('Recorded By')
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses_approved',
        verbose_name=_('Approved By')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Expense')
        verbose_name_plural = _('Expenses')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.voucher_number} | {self.category.name_en} | NPR {self.amount}"

    def clean(self):
        if not self.date_bs and self.date:
            bs_obj = ad_to_bs(self.date)
            if bs_obj:
                self.date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"
        if self.amount is not None and self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': _("Expense amount must be greater than zero.")})
