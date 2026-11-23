from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.station.models import FuelType, StorageTank
from common.date_utils import ad_to_bs


class Supplier(models.Model):
    """
    Petroleum and lubricant suppliers (e.g. Nepal Oil Corporation - NOC Amlekhgunj/Birgunj Depots).
    """
    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('INACTIVE', _('Inactive')),
    ]

    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name=_('Supplier / Depot Name')
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
        verbose_name=_('Depot Address / Location')
    )
    pan_vat_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_('PAN / VAT Number')
    )
    opening_payable_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Opening Payable Balance (NPR)'),
        help_text=_('Pre-existing unpaid balance owed to this supplier')
    )
    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Current Outstanding Payable (NPR)')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name=_('Supplier Status')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Supplier')
        verbose_name_plural = _('Suppliers')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (Payable: NPR {self.current_balance})"


class FuelPurchase(models.Model):
    """
    Tanker delivery / Fuel purchase receipt from supplier (NOC).
    Upon approval, triggers double-entry inventory ledger movements into StorageTank.
    """
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', _('Unpaid')),
        ('PARTIAL', _('Partially Paid')),
        ('PAID', _('Fully Paid')),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('PENDING', _('Pending Verification')),
        ('APPROVED', _('Approved & Inward Delivered')),
        ('REJECTED', _('Rejected')),
    ]

    invoice_number = models.CharField(
        max_length=60,
        db_index=True,
        verbose_name=_('Supplier Invoice / Challan #'),
        help_text=_('NOC Sales Invoice / Tanker Loading Challan Number')
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name=_('Supplier / Depot')
    )
    purchase_date = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Purchase Date (AD)')
    )
    purchase_date_bs = models.CharField(
        max_length=30,
        verbose_name=_('Purchase Date (BS)')
    )
    fuel_type = models.ForeignKey(
        FuelType,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name=_('Fuel Product')
    )
    receiving_tank = models.ForeignKey(
        StorageTank,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name=_('Receiving Storage Tank')
    )
    delivered_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Delivered Quantity (L)'),
        help_text=_('Net volume delivered into station tank (KL converted to Litres)')
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Purchase Rate / L (NPR)'),
        help_text=_('NOC invoice purchase price per litre')
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('VAT / Taxes (NPR)')
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_('Total Purchase Amount (NPR)')
    )
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Amount Paid (NPR)')
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNPAID',
        verbose_name=_('Payment Status')
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_('Approval Status')
    )
    tanker_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Tanker Truck # (गाडी नं.)'),
        help_text=_('e.g. Na 7 Kha 4521')
    )
    driver_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Tanker Driver Name')
    )
    chamber_dip_before = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Tank Dip Before Delivery (cm)')
    )
    chamber_dip_after = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Tank Dip After Delivery (cm)')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Delivery Remarks / Notes')
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchases_approved',
        verbose_name=_('Approved By')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='purchases_created',
        verbose_name=_('Recorded By')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Fuel Purchase')
        verbose_name_plural = _('Fuel Purchases')
        ordering = ['-purchase_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'invoice_number'],
                name='unique_supplier_invoice'
            )
        ]

    def __str__(self):
        return f"{self.invoice_number} | {self.supplier.name} | {self.fuel_type.code} {self.delivered_quantity} L"

    def clean(self):
        """
        Validate purchase constraints:
        1. Prevent assigning incompatible fuel to receiving tank.
        2. Auto-derive BS date.
        3. Calculate total amount if missing.
        """
        if self.receiving_tank and self.fuel_type:
            if self.receiving_tank.fuel_type != self.fuel_type:
                raise ValidationError({
                    'receiving_tank': _(
                        "Incompatible Fuel Type! Tank '%(tank)s' holds %(tank_fuel)s, "
                        "cannot receive %(purchase_fuel)s."
                    ) % {
                        'tank': self.receiving_tank.tank_name,
                        'tank_fuel': self.receiving_tank.fuel_type.name_en,
                        'purchase_fuel': self.fuel_type.name_en,
                    }
                })

        if not self.purchase_date_bs and self.purchase_date:
            bs_obj = ad_to_bs(self.purchase_date)
            if bs_obj:
                self.purchase_date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"

        if self.delivered_quantity and self.purchase_price:
            calc = (self.delivered_quantity * self.purchase_price) + (self.tax_amount or Decimal('0.00'))
            if not self.total_amount:
                self.total_amount = calc

    @property
    def outstanding_amount(self) -> Decimal:
        return max(self.total_amount - self.paid_amount, Decimal('0.00'))


class SupplierPayment(models.Model):
    """
    Payments made to supplier against purchase invoices or account balance.
    """
    PAYMENT_METHOD_CHOICES = [
        ('CASH', _('Cash Payment')),
        ('BANK_TRANSFER', _('Bank Transfer (IPS/RTGS)')),
        ('CHEQUE', _('Bank Cheque')),
    ]

    payment_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name=_('Payment Receipt #')
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('Supplier')
    )
    purchase = models.ForeignKey(
        FuelPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_('Against Purchase Invoice (Optional)')
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
        max_digits=14,
        decimal_places=2,
        verbose_name=_('Payment Amount (NPR)')
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name=_('Payment Method')
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Bank Reference / Cheque #')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name=_('Recorded By')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes / Remarks')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Supplier Payment')
        verbose_name_plural = _('Supplier Payments')
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"{self.payment_number} | {self.supplier.name} | NPR {self.amount}"

    def clean(self):
        if not self.payment_date_bs and self.payment_date:
            bs_obj = ad_to_bs(self.payment_date)
            if bs_obj:
                self.payment_date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"
