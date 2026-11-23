"""
Station, Fuel, Storage Tank, Dispensing Pump, Nozzle, and Fuel Price History Models.
Enforces business rules, tank capacity constraints, and fuel compatibility.
"""

from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings


# ==============================================================================
# 1. Station Configuration (Singleton)
# ==============================================================================

class StationConfiguration(models.Model):
    """
    Singleton model storing primary petrol station credentials, tax, and operating settings.
    """
    station_name_en = models.CharField(
        max_length=150,
        default='Basista Oil Traders',
        verbose_name=_('Station Name (English)')
    )
    station_name_ne = models.CharField(
        max_length=150,
        default='बसिस्ट आयल ट्रेडर्स',
        verbose_name=_('Station Name (Nepali)')
    )
    station_address_en = models.CharField(
        max_length=255,
        default='Kathmandu, Nepal',
        verbose_name=_('Address (English)')
    )
    station_address_ne = models.CharField(
        max_length=255,
        default='काठमाडौं, नेपाल',
        verbose_name=_('Address (Nepali)')
    )
    phone_number = models.CharField(
        max_length=50,
        default='01-4412345 / 9851011223',
        verbose_name=_('Phone Number')
    )
    email = models.EmailField(
        default='info@basistaoil.com.np',
        verbose_name=_('Official Email')
    )
    pan_vat_number = models.CharField(
        max_length=20,
        default='601234567',
        verbose_name=_('PAN / VAT Number'),
        help_text=_('Inland Revenue Department (IRD) Tax Registration Number')
    )
    logo = models.ImageField(
        upload_to='station_logos/',
        blank=True,
        null=True,
        verbose_name=_('Station Logo')
    )
    currency = models.CharField(
        max_length=10,
        default='NPR',
        choices=[('NPR', _('Nepalese Rupee (NPR / रु)'))],
        verbose_name=_('Currency')
    )
    timezone = models.CharField(
        max_length=50,
        default='Asia/Kathmandu',
        verbose_name=_('Operating Timezone')
    )
    default_language = models.CharField(
        max_length=5,
        choices=[('en', _('English')), ('ne', _('Nepali (नेपाली)'))],
        default='en',
        verbose_name=_('Default Language')
    )
    financial_year = models.CharField(
        max_length=20,
        default='2083/84',
        verbose_name=_('Current Fiscal Year (BS)'),
        help_text=_('Nepali fiscal year format (e.g. 2083/84)')
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Last Updated'))

    class Meta:
        verbose_name = _('Station Configuration')
        verbose_name_plural = _('Station Configuration')

    def __str__(self):
        return f"{self.station_name_en} ({self.station_name_ne})"

    @property
    def station_name(self) -> str:
        from django.utils.translation import get_language
        return self.station_name_ne if get_language() == 'ne' and self.station_name_ne else self.station_name_en

    @property
    def station_address(self) -> str:
        from django.utils.translation import get_language
        return self.station_address_ne if get_language() == 'ne' and self.station_address_ne else self.station_address_en

    def clean(self):
        # Enforce singleton pattern
        if not self.pk and StationConfiguration.objects.exists():
            raise ValidationError(_('Only one Station Configuration record is allowed.'))

    @classmethod
    def get_solo(cls):
        """Get or create the singleton instance."""
        config, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'station_name_en': 'Basista Oil Traders',
                'station_name_ne': 'बसिस्ट आयल ट्रेडर्स',
                'station_address_en': 'Kathmandu, Nepal',
                'station_address_ne': 'काठमाडौं, नेपाल',
                'phone_number': '01-4412345 / 9851011223',
                'email': 'info@basistaoil.com.np',
                'pan_vat_number': '601234567',
                'currency': 'NPR',
                'timezone': 'Asia/Kathmandu',
                'default_language': 'en',
                'financial_year': '2083/84',
            }
        )
        return config


# ==============================================================================
# 2. Fuel Configuration (Petrol & Diesel)
# ==============================================================================

class FuelType(models.Model):
    """
    Petroleum fuel product types (e.g. Petrol MS, Diesel HSD).
    """
    name_en = models.CharField(
        max_length=50,
        verbose_name=_('Fuel Name (English)'),
        help_text=_('e.g. Petrol (MS), Diesel (HSD)')
    )
    name_ne = models.CharField(
        max_length=50,
        verbose_name=_('Fuel Name (Nepali)'),
        help_text=_('e.g. पेट्रोल (MS), डिजेल (HSD)')
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Fuel Code'),
        help_text=_('Standard code: MS (Motor Spirit), HSD (High Speed Diesel)')
    )
    unit = models.CharField(
        max_length=20,
        default='Litre',
        verbose_name=_('Unit of Measurement')
    )
    color_code = models.CharField(
        max_length=20,
        default='#059669',
        verbose_name=_('Color Code (HEX)'),
        help_text=_('Visual color indicator (e.g. #059669 for Petrol, #1e3a8a for Diesel)')
    )
    badge_class = models.CharField(
        max_length=50,
        default='badge-petrol',
        verbose_name=_('Badge Style Class')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active Status')
    )
    display_order = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_('Display Order')
    )

    class Meta:
        verbose_name = _('Fuel Type')
        verbose_name_plural = _('Fuel Types')
        ordering = ['display_order', 'name_en']

    def __str__(self):
        return f"{self.name_en} ({self.code})"

    def get_current_price(self, as_of=None):
        """
        Fetch effective approved FuelPrice record at a given datetime.
        """
        return FuelPrice.get_effective_price(self, as_of_datetime=as_of)


# ==============================================================================
# 3. Storage Tank Management
# ==============================================================================

class StorageTank(models.Model):
    """
    Underground petroleum storage tank with capacity limits and safety stock threshold.
    """
    tank_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_('Tank Number / Code'),
        help_text=_('e.g. T-1, T-2')
    )
    tank_name = models.CharField(
        max_length=100,
        verbose_name=_('Tank Name / Description'),
        help_text=_('e.g. Underground Tank 1 (Petrol MS)')
    )
    fuel_type = models.ForeignKey(
        FuelType,
        on_delete=models.PROTECT,
        related_name='tanks',
        verbose_name=_('Fuel Type')
    )
    capacity_liters = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        verbose_name=_('Maximum Capacity (Litres)'),
        help_text=_('Total safe filling capacity in Litres (e.g. 15000.00)')
    )
    opening_stock = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Opening Stock (Litres)')
    )
    current_stock = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Stock (Litres)')
    )
    alert_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('1000.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Low Stock Alert Threshold (Litres)')
    )
    installation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Installation Date')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active Status')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Storage Tank')
        verbose_name_plural = _('Storage Tanks')
        ordering = ['tank_number']

    def __str__(self):
        return f"{self.tank_number}: {self.tank_name} ({self.fuel_type.code})"

    def clean(self):
        """
        Validate that stock quantities do not exceed tank maximum capacity.
        """
        if self.capacity_liters is not None:
            if self.opening_stock is not None and self.opening_stock > self.capacity_liters:
                raise ValidationError({
                    'opening_stock': _('Opening stock (%(stock)s L) cannot exceed maximum tank capacity (%(cap)s L).') % {
                        'stock': self.opening_stock,
                        'cap': self.capacity_liters
                    }
                })
            if self.current_stock is not None and self.current_stock > self.capacity_liters:
                raise ValidationError({
                    'current_stock': _('Current stock (%(stock)s L) cannot exceed maximum tank capacity (%(cap)s L).') % {
                        'stock': self.current_stock,
                        'cap': self.capacity_liters
                    }
                })

    @property
    def stock_percentage(self) -> float:
        """Percentage of fuel remaining in tank."""
        if not self.capacity_liters or self.capacity_liters <= 0:
            return 0.0
        return round(float(self.current_stock / self.capacity_liters) * 100, 1)

    @property
    def is_low_stock(self) -> bool:
        """Indicates if fuel level is below the re-order safety threshold."""
        return self.current_stock <= self.alert_threshold


# ==============================================================================
# 4. Dispensing Pumps Configuration
# ==============================================================================

class Pump(models.Model):
    """
    Electronic fuel dispensing unit / pump.
    """
    STATUS_CHOICES = [
        ('ACTIVE', _('Active / Dispensing')),
        ('MAINTENANCE', _('Under Maintenance')),
        ('INACTIVE', _('Inactive / Decommissioned')),
    ]

    pump_number = models.PositiveSmallIntegerField(
        unique=True,
        verbose_name=_('Pump Number'),
        help_text=_('Station pump index (e.g. 1, 2)')
    )
    pump_name = models.CharField(
        max_length=100,
        verbose_name=_('Pump Name / Label'),
        help_text=_('e.g. Dispensing Pump 1 (Dual)')
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Serial Number / ID')
    )
    model_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Manufacturer / Model'),
        help_text=_('e.g. Tokheim Quantium / Gilbarco Veeder-Root')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name=_('Operational Status')
    )
    installation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Installation Date')
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes / Remarks')
    )

    class Meta:
        verbose_name = _('Dispensing Pump')
        verbose_name_plural = _('Dispensing Pumps')
        ordering = ['pump_number']

    def __str__(self):
        return f"{_('Pump')} #{self.pump_number} ({self.pump_name})"

    @property
    def nozzles_count(self) -> int:
        return self.nozzles.count()

    @property
    def is_operational(self) -> bool:
        return self.status == 'ACTIVE'


# ==============================================================================
# 5. Nozzles Configuration
# ==============================================================================

class Nozzle(models.Model):
    """
    Fuel dispensing nozzle attached to a pump, connected to an underground tank.
    """
    STATUS_CHOICES = [
        ('ACTIVE', _('Active / Operational')),
        ('MAINTENANCE', _('Maintenance / Calibration')),
        ('BLOCKED', _('Blocked')),
        ('INACTIVE', _('Inactive')),
    ]

    pump = models.ForeignKey(
        Pump,
        on_delete=models.PROTECT,
        related_name='nozzles',
        verbose_name=_('Dispensing Pump')
    )
    nozzle_number = models.PositiveSmallIntegerField(
        verbose_name=_('Nozzle Number on Pump'),
        help_text=_('Position on the pump (e.g. 1, 2, 3, 4)')
    )
    nozzle_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_('Nozzle Code'),
        help_text=_('Unique station nozzle identifier (e.g. P1-N1, P1-N2)')
    )
    fuel_type = models.ForeignKey(
        FuelType,
        on_delete=models.PROTECT,
        related_name='nozzles',
        verbose_name=_('Dispensed Fuel Type')
    )
    tank = models.ForeignKey(
        StorageTank,
        on_delete=models.PROTECT,
        related_name='nozzles',
        verbose_name=_('Connected Storage Tank')
    )
    current_meter_reading = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Totalizer Meter Reading (L)'),
        help_text=_('Cumulative electronic/mechanical meter reading in Litres')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name=_('Nozzle Status')
    )
    installation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Installation Date')
    )

    class Meta:
        verbose_name = _('Dispensing Nozzle')
        verbose_name_plural = _('Dispensing Nozzles')
        ordering = ['pump', 'nozzle_number']
        constraints = [
            models.UniqueConstraint(
                fields=['pump', 'nozzle_number'],
                name='unique_nozzle_per_pump'
            )
        ]

    def __str__(self):
        return f"{self.nozzle_code} - {self.pump.pump_name} ({self.fuel_type.code})"

    def clean(self):
        """
        Enforce fuel compatibility rule:
        Prevent assigning incompatible fuel types (e.g. Petrol nozzle linked to Diesel tank).
        """
        if self.tank and self.fuel_type:
            if self.tank.fuel_type != self.fuel_type:
                raise ValidationError({
                    'tank': _(
                        "Incompatible Fuel Type! Tank '%(tank)s' holds %(tank_fuel)s, "
                        "which cannot be connected to a %(nozzle_fuel)s nozzle."
                    ) % {
                        'tank': self.tank.tank_name,
                        'tank_fuel': self.tank.fuel_type.name_en,
                        'nozzle_fuel': self.fuel_type.name_en,
                    }
                })


# ==============================================================================
# 6. Fuel Price Management
# ==============================================================================

class FuelPrice(models.Model):
    """
    Auditable fuel price history tracking official NOC revisions,
    purchase rates, retail selling rates, and approval workflow.
    """
    STATUS_CHOICES = [
        ('APPROVED', _('Approved & Effective')),
        ('PENDING', _('Pending Approval')),
        ('REJECTED', _('Rejected')),
    ]

    fuel_type = models.ForeignKey(
        FuelType,
        on_delete=models.PROTECT,
        related_name='prices',
        verbose_name=_('Fuel Type')
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Purchase Price / Ltr (NPR)'),
        help_text=_('Dealer purchase rate from Nepal Oil Corporation (NOC)')
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Retail Selling Price / Ltr (NPR)'),
        help_text=_('Dealer retail consumer selling price per Litre')
    )
    effective_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Effective Date & Time'),
        help_text=_('Date and time from which this price takes effect')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='prices_created',
        verbose_name=_('Created By')
    )
    approval_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='APPROVED',
        verbose_name=_('Approval Status')
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prices_approved',
        verbose_name=_('Approved By')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Circular / Reference Notes'),
        help_text=_('e.g. NOC circular no. 2083/08')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Fuel Price')
        verbose_name_plural = _('Fuel Price Revisions')
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['fuel_type', 'effective_date', 'approval_status']),
        ]

    def __str__(self):
        return f"{self.fuel_type.code} - NPR {self.selling_price}/L (from {self.effective_date.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        if self.purchase_price and self.selling_price:
            if self.selling_price < self.purchase_price:
                raise ValidationError({
                    'selling_price': _('Selling price cannot be lower than purchase price.')
                })

    @property
    def margin_per_liter(self) -> Decimal:
        """Dealer gross profit margin per Litre."""
        if self.selling_price is not None and self.purchase_price is not None:
            return self.selling_price - self.purchase_price
        return Decimal('0.00')

    @classmethod
    def get_effective_price(cls, fuel_type, as_of_datetime=None):
        """
        Return the latest approved FuelPrice for given fuel_type active at as_of_datetime.
        Guarantees accurate historical pricing for past sales transactions.
        """
        if as_of_datetime is None:
            as_of_datetime = timezone.now()

        return cls.objects.filter(
            fuel_type=fuel_type,
            approval_status='APPROVED',
            effective_date__lte=as_of_datetime
        ).order_by('-effective_date').first()
