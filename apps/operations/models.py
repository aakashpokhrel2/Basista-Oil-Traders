"""
Models for Shift Management, Meter Readings, Fuel Sales, and Auditable Stock Movement Ledger.
Enforces transactional integrity, negative reading prevention, and stock audit trails.
"""

from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from apps.station.models import FuelType, StorageTank, Pump, Nozzle, FuelPrice
from common.date_utils import ad_to_bs, format_bs_date


# ==============================================================================
# 1. Shift Schedule & Shift Management
# ==============================================================================

class ShiftSchedule(models.Model):
    """
    Station operational shift timetable (e.g. Morning, Evening, Night).
    """
    name_en = models.CharField(
        max_length=100,
        verbose_name=_('Shift Name (English)'),
        help_text=_('e.g. Day Shift (06:00 - 14:00)')
    )
    name_ne = models.CharField(
        max_length=100,
        verbose_name=_('Shift Name (Nepali)'),
        help_text=_('e.g. दिवा सिफ्ट (०६:०० - १४:००)')
    )
    start_time = models.TimeField(verbose_name=_('Scheduled Start Time'))
    end_time = models.TimeField(verbose_name=_('Scheduled End Time'))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))

    class Meta:
        verbose_name = _('Shift Schedule')
        verbose_name_plural = _('Shift Schedules')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.name_en} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class Shift(models.Model):
    """
    Daily working shift session tracking employee assignments, cash drawer, and reconciliation.
    """
    STATUS_CHOICES = [
        ('OPEN', _('Open / Active')),
        ('CLOSED', _('Closed (Pending Approval)')),
        ('APPROVED', _('Approved & Reconciled')),
    ]

    shift_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Shift Number'),
        help_text=_('e.g. S-2083-0807-1')
    )
    schedule = models.ForeignKey(
        ShiftSchedule,
        on_delete=models.PROTECT,
        related_name='shifts',
        verbose_name=_('Shift Schedule')
    )
    date_ad = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Date (AD)')
    )
    date_bs = models.CharField(
        max_length=30,
        verbose_name=_('Date (BS)'),
        help_text=_('e.g. 2083-08-07')
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='supervised_shifts',
        verbose_name=_('Shift Supervisor / Manager')
    )
    operators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_shifts',
        verbose_name=_('Assigned Pump Operators / Cashiers')
    )
    opening_time = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Shift Opening Time')
    )
    closing_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Shift Closing Time')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN',
        db_index=True,
        verbose_name=_('Shift Status')
    )
    opening_cash_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Opening Cash Balance (NPR)'),
        help_text=_('Cash float provided in drawer at shift start')
    )
    closing_cash_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Physical Cash Counted at Close (NPR)'),
        help_text=_('Actual physical cash counted in drawer at shift end')
    )
    actual_cash_collected = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Cash Handed Over (NPR)'),
        help_text=_('Net cash handed over to safe / manager')
    )
    expected_cash_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Expected Cash Balance (NPR)'),
        help_text=_('Calculated: Opening cash + Cash fuel sales')
    )
    cash_difference = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Cash Variance (NPR)'),
        help_text=_('Difference: Closing cash - Expected cash (Shortage or Overage)')
    )
    handover_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Cash Handover Notes / Remarks')
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_shifts',
        verbose_name=_('Approved By')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Shift')
        verbose_name_plural = _('Shifts')
        ordering = ['-opening_time']

    def __str__(self):
        return f"{self.shift_number} ({self.schedule.name_en}) - {self.get_status_display()}"

    def clean(self):
        """
        Validate business rules:
        1. Auto-derive BS date if empty.
        2. Prevent overlapping active (OPEN) shifts if prohibited.
        """
        if not self.date_bs and self.date_ad:
            bs_obj = ad_to_bs(self.date_ad)
            self.date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"

        # Prevent more than 1 OPEN shift on the same station pump island simultaneously
        if self.status == 'OPEN':
            overlapping_shifts = Shift.objects.filter(status='OPEN')
            if self.pk:
                overlapping_shifts = overlapping_shifts.exclude(pk=self.pk)
            # Check if supervisor already has an open shift
            if self.supervisor and overlapping_shifts.filter(supervisor=self.supervisor).exists():
                raise ValidationError({
                    'supervisor': _("Supervisor '%(name)s' already has an active open shift.") % {
                        'name': self.supervisor.get_full_name() or self.supervisor.username
                    }
                })

    @property
    def is_open(self) -> bool:
        return self.status == 'OPEN'

    @property
    def is_closed(self) -> bool:
        return self.status in ['CLOSED', 'APPROVED']

    @property
    def has_cash_shortage(self) -> bool:
        return self.cash_difference < Decimal('0.00')

    @property
    def has_cash_excess(self) -> bool:
        return self.cash_difference > Decimal('0.00')


# ==============================================================================
# 2. Meter Reading Management
# ==============================================================================

class MeterReading(models.Model):
    """
    Cumulative electronic and mechanical meter readings logged per nozzle per shift.
    Quantity Sold = Closing Reading - Opening Reading - Calibration Test Quantity.
    """
    nozzle = models.ForeignKey(
        Nozzle,
        on_delete=models.PROTECT,
        related_name='meter_readings',
        verbose_name=_('Dispensing Nozzle')
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name='meter_readings',
        verbose_name=_('Working Shift')
    )
    opening_meter_reading = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Opening Meter Reading (L)'),
        help_text=_('Totalizer reading at shift commencement')
    )
    closing_meter_reading = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Closing Meter Reading (L)'),
        help_text=_('Totalizer reading at shift conclusion')
    )
    test_dispense_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Calibration / Testing Quantity (L)'),
        help_text=_('Fuel dispensed into test measure can and poured back into storage tank')
    )
    quantity_sold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Gross Dispensed Quantity (L)'),
        help_text=_('Closing Reading - Opening Reading')
    )
    net_quantity_sold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Net Quantity Sold (L)'),
        help_text=_('Gross Quantity - Testing Dispense Quantity')
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Unit Selling Rate (NPR/L)'),
        help_text=_('Effective retail price at time of shift')
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Total Sales Value (NPR)'),
        help_text=_('Net Quantity Sold * Unit Selling Rate')
    )
    reading_timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Reading Timestamp')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='meter_readings_recorded',
        verbose_name=_('Recorded By')
    )
    is_rollover = models.BooleanField(
        default=False,
        verbose_name=_('Meter Rollover / Totalizer Reset Flag'),
        help_text=_('Mark true if mechanical/electronic totalizer rolled over 999999 or was replaced')
    )
    rollover_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Rollover / Reset Authorization Notes')
    )
    rollover_authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rollover_authorizations',
        verbose_name=_('Rollover Authorized By')
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Notes / Remarks')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Meter Reading')
        verbose_name_plural = _('Meter Readings')
        ordering = ['-reading_timestamp']
        constraints = [
            models.UniqueConstraint(
                fields=['shift', 'nozzle'],
                name='unique_nozzle_reading_per_shift'
            )
        ]

    def __str__(self):
        return f"{self.nozzle.nozzle_code} | Shift: {self.shift.shift_number} | Net: {self.net_quantity_sold} L"

    def clean(self):
        """
        Validate business rules:
        1. Closing reading cannot be less than opening reading unless authorized rollover.
        2. Automatic calculation of gross quantity, net quantity, and total amount.
        """
        if self.closing_meter_reading is not None and self.opening_meter_reading is not None:
            if self.closing_meter_reading < self.opening_meter_reading:
                if not self.is_rollover:
                    raise ValidationError({
                        'closing_meter_reading': _(
                            "Negative Meter Reading Error! Closing reading (%(close)s L) cannot be less than "
                            "opening reading (%(open)s L). If the meter counter rolled over, select 'Meter Rollover' "
                            "and obtain managerial authorization."
                        ) % {
                            'close': self.closing_meter_reading,
                            'open': self.opening_meter_reading
                        }
                    })
                elif not self.rollover_authorized_by:
                    raise ValidationError({
                        'rollover_authorized_by': _("Managerial authorization is mandatory when documenting a meter rollover.")
                    })

            # Calculate gross dispensed quantity
            if self.is_rollover:
                # Standard mechanical/electronic totalizer cycle rollover at 99,999.99
                max_cycle = Decimal('99999.99')
                gross_qty = (max_cycle - self.opening_meter_reading) + self.closing_meter_reading
            else:
                gross_qty = self.closing_meter_reading - self.opening_meter_reading

            self.quantity_sold = max(gross_qty, Decimal('0.00'))

            # Net quantity after calibration returns
            test_qty = self.test_dispense_quantity or Decimal('0.00')
            if test_qty > self.quantity_sold:
                raise ValidationError({
                    'test_dispense_quantity': _("Test dispense quantity (%(test)s L) cannot exceed gross dispensed fuel (%(gross)s L).") % {
                        'test': test_qty,
                        'gross': self.quantity_sold
                    }
                })

            self.net_quantity_sold = self.quantity_sold - test_qty

            # Calculate total amount
            if self.unit_price is not None:
                self.total_amount = (self.net_quantity_sold * self.unit_price).quantize(Decimal('0.01'))


# ==============================================================================
# 3. Fuel Sales Management (Meter-Based & Manual)
# ==============================================================================

class FuelSale(models.Model):
    """
    Sales ledger record tracking each fuel sale transaction (Petrol/Diesel, Cash/Credit/Bank).
    Distinctly differentiates meter-based aggregate shift sales from manual sales entries.
    """
    SALE_TYPE_CHOICES = [
        ('METER', _('Meter-based Dispense')),
        ('MANUAL', _('Manual Sales Entry')),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('CASH', _('Cash Payment (नगद)')),
        ('CREDIT', _('Customer Credit Account (उधारो)')),
        ('BANK_TRANSFER', _('Bank Transfer / Cheque (बैंक/चेक)')),
        ('QR_FONEPAY', _('Digital QR / Fonepay (डिजिटल क्यूआर)')),
    ]

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_('Invoice / Bill Number'),
        help_text=_('e.g. INV-2083-00001')
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name=_('Working Shift')
    )
    sale_type = models.CharField(
        max_length=20,
        choices=SALE_TYPE_CHOICES,
        default='METER',
        db_index=True,
        verbose_name=_('Sale Type')
    )
    fuel_type = models.ForeignKey(
        FuelType,
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name=_('Fuel Product')
    )
    nozzle = models.ForeignKey(
        Nozzle,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name=_('Dispensing Nozzle')
    )
    tank = models.ForeignKey(
        StorageTank,
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name=_('Source Storage Tank')
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Dispensed Quantity (L)'),
        help_text=_('Volume of fuel sold in Litres')
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Unit Selling Rate (NPR/L)'),
        help_text=_('Preserved historical retail price')
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Total Sale Amount (NPR)')
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default='CASH',
        db_index=True,
        verbose_name=_('Payment Method')
    )
    customer_name = models.CharField(
        max_length=150,
        default='Walk-in Customer / खुद्रा ग्राहक',
        verbose_name=_('Customer Name / Account')
    )
    vehicle_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Vehicle Plate Number'),
        help_text=_('e.g. Ba 2 Kha 4567')
    )
    reason_for_manual = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Reason for Manual Entry'),
        help_text=_('Mandatory justification when recording manual fuel sales')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sales_recorded',
        verbose_name=_('Recorded By')
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_authorized',
        verbose_name=_('Authorized By (for Manual Entry)')
    )
    transaction_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Transaction Date & Time')
    )

    # Cancellation & Reversal audit fields
    is_cancelled = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_('Is Cancelled / Voided')
    )
    cancellation_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Cancellation Reason')
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_cancelled',
        verbose_name=_('Cancelled By')
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Cancelled At')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Fuel Sale')
        verbose_name_plural = _('Fuel Sales')
        ordering = ['-transaction_date']

    def __str__(self):
        return f"{self.invoice_number} | {self.fuel_type.code} | {self.quantity} L | NPR {self.total_amount}"

    def clean(self):
        """
        Validate sales transactions:
        1. Manual sale requires documented reason.
        2. Total amount must match quantity * unit_price.
        """
        if self.sale_type == 'MANUAL':
            if not self.reason_for_manual or not self.reason_for_manual.strip():
                raise ValidationError({
                    'reason_for_manual': _("Reason is mandatory for manual fuel sales entries.")
                })

        if self.quantity and self.unit_price:
            calc_total = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
            if not self.total_amount:
                self.total_amount = calc_total

    @property
    def is_manual_sale(self) -> bool:
        return self.sale_type == 'MANUAL'

    @property
    def is_cash(self) -> bool:
        return self.payment_method == 'CASH'

    @property
    def is_credit(self) -> bool:
        return self.payment_method == 'CREDIT'


# ==============================================================================
# 4. Auditable Stock Movement Ledger
# ==============================================================================

class StockMovement(models.Model):
    """
    Immutable stock ledger recording every addition, deduction, transfer,
    and adjustment across station underground storage tanks.
    Formula: Expected Closing Stock = Opening Stock + Inflow - Outflow + Adjustments.
    """
    MOVEMENT_TYPE_CHOICES = [
        ('OPENING', _('Initial Opening Stock')),
        ('PURCHASE', _('Tanker Receipt / Purchase Delivery')),
        ('SALE_METER', _('Meter-based Sales Dispense')),
        ('SALE_MANUAL', _('Manual Sales Dispense')),
        ('SALE_REVERSAL', _('Sales Cancellation Reversal')),
        ('TRANSFER_IN', _('Tank Transfer In (+)')),
        ('TRANSFER_OUT', _('Tank Transfer Out (-)')),
        ('TEST_RETURN', _('Calibration / Testing Return (+)')),
        ('ADJUSTMENT_LOSS', _('Evaporation / Dip Loss (-)')),
        ('ADJUSTMENT_GAIN', _('Calibration / Dip Gain (+)')),
    ]

    DIRECTION_CHOICES = [
        ('IN', _('Stock In (+)')),
        ('OUT', _('Stock Out (-)')),
    ]

    tank = models.ForeignKey(
        StorageTank,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name=_('Storage Tank')
    )
    movement_type = models.CharField(
        max_length=30,
        choices=MOVEMENT_TYPE_CHOICES,
        db_index=True,
        verbose_name=_('Movement Type')
    )
    direction = models.CharField(
        max_length=5,
        choices=DIRECTION_CHOICES,
        verbose_name=_('Flow Direction')
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Quantity (L)'),
        help_text=_('Quantity of fuel moved')
    )
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Tank Opening Balance (L)'),
        help_text=_('Stock level before this movement')
    )
    closing_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Tank Closing Balance (L)'),
        help_text=_('Stock level immediately after this movement')
    )
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Reference Entity'),
        help_text=_('e.g. FuelSale, MeterReading, TankerInvoice')
    )
    reference_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Reference ID / Invoice #'),
        help_text=_('e.g. INV-2083-00001, S-2083-0807-1')
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name=_('Working Shift')
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_movements_performed',
        verbose_name=_('Performed By')
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Timestamp')
    )
    remarks = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Audit Remarks / Notes')
    )

    class Meta:
        verbose_name = _('Stock Movement')
        verbose_name_plural = _('Stock Movement Ledger')
        ordering = ['-timestamp', '-id']

    def __str__(self):
        sign = '+' if self.direction == 'IN' else '-'
        return f"{self.tank.tank_number} | {self.get_movement_type_display()} | {sign}{self.quantity} L -> Bal: {self.closing_balance} L"
