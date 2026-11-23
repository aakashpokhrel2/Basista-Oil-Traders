"""
Automated unit tests for Station Configuration, Fuel Types, Storage Tanks,
Dispensing Pumps, Nozzles, and Fuel Price History (Phase 2).
"""

from decimal import Decimal
from datetime import timedelta, date
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.authentication.models import User
from apps.station.models import (
    StationConfiguration,
    FuelType,
    StorageTank,
    Pump,
    Nozzle,
    FuelPrice,
)
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_PUMP_OPERATOR
from common.date_utils import (
    get_bs_month_date_range,
    get_current_fiscal_year_bs,
    get_fiscal_year_date_range,
    ad_to_bs,
    bs_to_ad,
)


class StationConfigurationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='owner_station',
            password='Password123!',
            role=ROLE_OWNER,
        )
        self.operator = User.objects.create_user(
            username='operator_station',
            password='Password123!',
            role=ROLE_PUMP_OPERATOR,
        )

        # Base fuel types
        self.petrol, _ = FuelType.objects.get_or_create(
            code='MS',
            defaults={
                'name_en': 'Petrol (MS)',
                'name_ne': 'पेट्रोल (MS)',
                'unit': 'Litre',
                'color_code': '#059669',
            }
        )
        self.diesel, _ = FuelType.objects.get_or_create(
            code='HSD',
            defaults={
                'name_en': 'Diesel (HSD)',
                'name_ne': 'डिजेल (HSD)',
                'unit': 'Litre',
                'color_code': '#1e3a8a',
            }
        )

    def test_station_configuration_singleton(self):
        """Verify singleton pattern: only 1 configuration record allowed."""
        config1 = StationConfiguration.get_solo()
        self.assertEqual(config1.pk, 1)

        # Attempting to create another record manually should raise ValidationError
        config2 = StationConfiguration(station_name_en='Duplicate Station')
        with self.assertRaises(ValidationError):
            config2.clean()

    def test_tank_capacity_validation(self):
        """Verify tank opening/current stock cannot exceed capacity and capacity must be positive."""
        # 1. Valid tank
        tank = StorageTank(
            tank_number='T-TEST1',
            tank_name='Test Petrol Tank',
            fuel_type=self.petrol,
            capacity_liters=Decimal('10000.00'),
            opening_stock=Decimal('5000.00'),
            current_stock=Decimal('5000.00'),
        )
        tank.full_clean()
        tank.save()
        self.assertEqual(tank.stock_percentage, 50.0)

        # 2. Opening stock exceeding capacity
        invalid_tank = StorageTank(
            tank_number='T-TEST2',
            tank_name='Overfilled Tank',
            fuel_type=self.petrol,
            capacity_liters=Decimal('10000.00'),
            opening_stock=Decimal('12000.00'),
            current_stock=Decimal('5000.00'),
        )
        with self.assertRaises(ValidationError):
            invalid_tank.clean()

        # 3. Current stock exceeding capacity
        invalid_tank2 = StorageTank(
            tank_number='T-TEST3',
            tank_name='Overfilled Current Tank',
            fuel_type=self.petrol,
            capacity_liters=Decimal('10000.00'),
            opening_stock=Decimal('5000.00'),
            current_stock=Decimal('15000.00'),
        )
        with self.assertRaises(ValidationError):
            invalid_tank2.clean()

    def test_fuel_compatibility_validation(self):
        """Prevent assigning incompatible fuel types between tank and nozzle."""
        petrol_tank = StorageTank.objects.create(
            tank_number='T-P1',
            tank_name='Petrol Tank',
            fuel_type=self.petrol,
            capacity_liters=Decimal('10000.00'),
            opening_stock=Decimal('5000.00'),
            current_stock=Decimal('5000.00'),
        )

        pump = Pump.objects.create(pump_number=10, pump_name='Test Pump')

        # Compatible nozzle: Petrol nozzle linked to Petrol tank -> SUCCESS
        valid_nozzle = Nozzle(
            pump=pump,
            nozzle_number=1,
            nozzle_code='P10-N1',
            fuel_type=self.petrol,
            tank=petrol_tank,
            current_meter_reading=Decimal('100.00'),
        )
        valid_nozzle.full_clean()
        valid_nozzle.save()
        self.assertEqual(valid_nozzle.fuel_type.code, 'MS')

        # Incompatible nozzle: Diesel nozzle linked to Petrol tank -> VALIDATION ERROR
        incompatible_nozzle = Nozzle(
            pump=pump,
            nozzle_number=2,
            nozzle_code='P10-N2',
            fuel_type=self.diesel,  # Diesel fuel!
            tank=petrol_tank,        # Petrol tank!
            current_meter_reading=Decimal('200.00'),
        )
        with self.assertRaises(ValidationError):
            incompatible_nozzle.clean()

    def test_pump_nozzle_relationship(self):
        """Pumps should support multiple nozzles and enforce uniqueness per position."""
        pump = Pump.objects.create(pump_number=20, pump_name='Dual Pump 20')
        tank = StorageTank.objects.create(
            tank_number='T-D1',
            tank_name='Diesel Tank',
            fuel_type=self.diesel,
            capacity_liters=Decimal('15000.00'),
            opening_stock=Decimal('8000.00'),
            current_stock=Decimal('8000.00'),
        )

        n1 = Nozzle.objects.create(
            pump=pump,
            nozzle_number=1,
            nozzle_code='P20-N1',
            fuel_type=self.diesel,
            tank=tank,
        )
        n2 = Nozzle.objects.create(
            pump=pump,
            nozzle_number=2,
            nozzle_code='P20-N2',
            fuel_type=self.diesel,
            tank=tank,
        )
        self.assertEqual(pump.nozzles.count(), 2)
        self.assertEqual(pump.nozzles_count, 2)

    def test_historical_fuel_price_resolution(self):
        """Historical prices must remain accurately retrievable at any past timestamp."""
        now = timezone.now()
        date_30_days_ago = now - timedelta(days=30)
        date_10_days_ago = now - timedelta(days=10)

        # Price 1 (effective 30 days ago): Rs 170
        p1 = FuelPrice.objects.create(
            fuel_type=self.petrol,
            purchase_price=Decimal('162.00'),
            selling_price=Decimal('170.00'),
            effective_date=date_30_days_ago,
            created_by=self.owner,
            approval_status='APPROVED',
            approved_by=self.owner,
            approved_at=date_30_days_ago,
        )

        # Price 2 (effective 10 days ago): Rs 175
        p2 = FuelPrice.objects.create(
            fuel_type=self.petrol,
            purchase_price=Decimal('166.50'),
            selling_price=Decimal('175.00'),
            effective_date=date_10_days_ago,
            created_by=self.owner,
            approval_status='APPROVED',
            approved_by=self.owner,
            approved_at=date_10_days_ago,
        )

        # Selling price cannot be lower than purchase price
        with self.assertRaises(ValidationError):
            invalid_p = FuelPrice(
                fuel_type=self.petrol,
                purchase_price=Decimal('170.00'),
                selling_price=Decimal('160.00'),
                created_by=self.owner,
            )
            invalid_p.clean()

        # Margin calculation
        self.assertEqual(p2.margin_per_liter, Decimal('8.50'))

        # Query effective price 20 days ago (between p1 and p2) -> should return p1 (Rs 170)
        date_20_days_ago = now - timedelta(days=20)
        eff_past = FuelPrice.get_effective_price(self.petrol, as_of_datetime=date_20_days_ago)
        self.assertEqual(eff_past.selling_price, Decimal('170.00'))

        # Query effective price today -> should return p2 (Rs 175)
        eff_today = FuelPrice.get_effective_price(self.petrol)
        self.assertEqual(eff_today.selling_price, Decimal('175.00'))

    def test_bs_month_date_range_filtering(self):
        """Test BS month range calculation for database queries."""
        start_ad, end_ad = get_bs_month_date_range(2083, 8)
        self.assertEqual(start_ad, date(2026, 11, 17))
        self.assertEqual(end_ad, date(2026, 12, 15))

        fy = get_current_fiscal_year_bs(date(2026, 11, 23))
        self.assertEqual(fy, '2083/84')
        fy_start, fy_end = get_fiscal_year_date_range('2083/84')
        self.assertTrue(fy_start < fy_end)

    def test_station_crud_views_access_control(self):
        """Ensure RBAC permissions on station configuration views."""
        # Operator cannot access station settings
        self.client.login(username='operator_station', password='Password123!')
        r = self.client.get(reverse('station:settings'))
        self.assertRedirects(r, reverse('dashboard:index'))
        self.client.logout()

        # Owner has access to all station pages
        self.client.login(username='owner_station', password='Password123!')

        # Settings
        r_settings = self.client.get(reverse('station:settings'))
        self.assertEqual(r_settings.status_code, 200)
        self.assertContains(r_settings, 'Station Profile &amp; Configuration')

        # Fuels
        r_fuels = self.client.get(reverse('station:fuel_list'))
        self.assertEqual(r_fuels.status_code, 200)
        self.assertContains(r_fuels, 'Petrol (MS)')

        # Tanks
        r_tanks = self.client.get(reverse('station:tank_list'))
        self.assertEqual(r_tanks.status_code, 200)

        # Pumps
        r_pumps = self.client.get(reverse('station:pump_list'))
        self.assertEqual(r_pumps.status_code, 200)

        # Prices
        r_prices = self.client.get(reverse('station:price_list'))
        self.assertEqual(r_prices.status_code, 200)
        self.assertContains(r_prices, 'Fuel Price Revisions & History')
