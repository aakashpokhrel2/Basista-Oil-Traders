"""
Seed initial Phase 2 Station Configuration, Fuel Types, Storage Tanks, Pumps, Nozzles, and Prices.
"""

from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.station.models import (
    StationConfiguration,
    FuelType,
    StorageTank,
    Pump,
    Nozzle,
    FuelPrice,
)
from apps.authentication.models import User


class Command(BaseCommand):
    help = 'Seeds Phase 2 station configuration, fuels, tanks, pumps, nozzles, and fuel prices.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing Phase 2 station assets..."))

        # 1. Station configuration
        config = StationConfiguration.get_solo()
        self.stdout.write(self.style.SUCCESS(f"  + Station: {config.station_name_en} ({config.station_name_ne})"))

        # 2. Fuel Types
        petrol, _ = FuelType.objects.get_or_create(
            code='MS',
            defaults={
                'name_en': 'Petrol (MS)',
                'name_ne': 'पेट्रोल (MS)',
                'unit': 'Litre',
                'color_code': '#059669',
                'badge_class': 'badge-petrol',
                'display_order': 1,
                'is_active': True,
            }
        )
        diesel, _ = FuelType.objects.get_or_create(
            code='HSD',
            defaults={
                'name_en': 'Diesel (HSD)',
                'name_ne': 'डिजेल (HSD)',
                'unit': 'Litre',
                'color_code': '#1e3a8a',
                'badge_class': 'badge-diesel',
                'display_order': 2,
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS("  + Fuel Types: Petrol (MS) and Diesel (HSD)"))

        # 3. Storage Tanks
        tank1, t1_created = StorageTank.objects.get_or_create(
            tank_number='T-1',
            defaults={
                'tank_name': 'Underground Tank 1 (Petrol MS)',
                'fuel_type': petrol,
                'capacity_liters': Decimal('15000.00'),
                'opening_stock': Decimal('8500.00'),
                'current_stock': Decimal('8500.00'),
                'alert_threshold': Decimal('1500.00'),
                'is_active': True,
            }
        )
        tank2, t2_created = StorageTank.objects.get_or_create(
            tank_number='T-2',
            defaults={
                'tank_name': 'Underground Tank 2 (Diesel HSD)',
                'fuel_type': diesel,
                'capacity_liters': Decimal('20000.00'),
                'opening_stock': Decimal('12400.00'),
                'current_stock': Decimal('12400.00'),
                'alert_threshold': Decimal('2000.00'),
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"  + Tanks: {tank1.tank_number} (Petrol) & {tank2.tank_number} (Diesel)"))

        # 4. Dispensing Pumps
        pump1, _ = Pump.objects.get_or_create(
            pump_number=1,
            defaults={
                'pump_name': 'Dispensing Pump 1 (Dual)',
                'serial_number': 'TK-2026-001',
                'model_name': 'Tokheim Quantium Dual',
                'status': 'ACTIVE',
            }
        )
        pump2, _ = Pump.objects.get_or_create(
            pump_number=2,
            defaults={
                'pump_name': 'Dispensing Pump 2 (Dual)',
                'serial_number': 'GVR-2026-002',
                'model_name': 'Gilbarco Veeder-Root Dual',
                'status': 'ACTIVE',
            }
        )
        self.stdout.write(self.style.SUCCESS("  + Dispensing Pumps: Pump 1 & Pump 2"))

        # 5. Dispensing Nozzles
        # Pump 1: Nozzle 1 (Petrol), Nozzle 2 (Diesel)
        n1, _ = Nozzle.objects.get_or_create(
            nozzle_code='P1-N1',
            defaults={
                'pump': pump1,
                'nozzle_number': 1,
                'fuel_type': petrol,
                'tank': tank1,
                'current_meter_reading': Decimal('12450.00'),
                'status': 'ACTIVE',
            }
        )
        n2, _ = Nozzle.objects.get_or_create(
            nozzle_code='P1-N2',
            defaults={
                'pump': pump1,
                'nozzle_number': 2,
                'fuel_type': diesel,
                'tank': tank2,
                'current_meter_reading': Decimal('18920.00'),
                'status': 'ACTIVE',
            }
        )
        # Pump 2: Nozzle 1 (Petrol), Nozzle 2 (Diesel)
        n3, _ = Nozzle.objects.get_or_create(
            nozzle_code='P2-N1',
            defaults={
                'pump': pump2,
                'nozzle_number': 1,
                'fuel_type': petrol,
                'tank': tank1,
                'current_meter_reading': Decimal('8430.00'),
                'status': 'ACTIVE',
            }
        )
        n4, _ = Nozzle.objects.get_or_create(
            nozzle_code='P2-N2',
            defaults={
                'pump': pump2,
                'nozzle_number': 2,
                'fuel_type': diesel,
                'tank': tank2,
                'current_meter_reading': Decimal('14680.00'),
                'status': 'ACTIVE',
            }
        )
        self.stdout.write(self.style.SUCCESS("  + Nozzles: P1-N1 (Petrol), P1-N2 (Diesel), P2-N1 (Petrol), P2-N2 (Diesel)"))

        # 6. Fuel Prices (Historical + Current)
        owner_user = User.objects.filter(role='OWNER').first()
        if not owner_user:
            owner_user = User.objects.first()

        now = timezone.now()
        past_date = now - timedelta(days=30)

        # Historical price (30 days ago)
        FuelPrice.objects.get_or_create(
            fuel_type=petrol,
            effective_date=past_date,
            defaults={
                'purchase_price': Decimal('162.00'),
                'selling_price': Decimal('170.00'),
                'created_by': owner_user,
                'approval_status': 'APPROVED',
                'approved_by': owner_user,
                'approved_at': past_date,
                'notes': 'NOC circular dated 2083-07-01',
            }
        )
        FuelPrice.objects.get_or_create(
            fuel_type=diesel,
            effective_date=past_date,
            defaults={
                'purchase_price': Decimal('150.00'),
                'selling_price': Decimal('158.00'),
                'created_by': owner_user,
                'approval_status': 'APPROVED',
                'approved_by': owner_user,
                'approved_at': past_date,
                'notes': 'NOC circular dated 2083-07-01',
            }
        )

        # Current price (effective 15 days ago)
        current_date = now - timedelta(days=15)
        FuelPrice.objects.get_or_create(
            fuel_type=petrol,
            effective_date=current_date,
            defaults={
                'purchase_price': Decimal('166.50'),
                'selling_price': Decimal('175.00'),
                'created_by': owner_user,
                'approval_status': 'APPROVED',
                'approved_by': owner_user,
                'approved_at': current_date,
                'notes': 'NOC circular dated 2083-07-16',
            }
        )
        FuelPrice.objects.get_or_create(
            fuel_type=diesel,
            effective_date=current_date,
            defaults={
                'purchase_price': Decimal('154.00'),
                'selling_price': Decimal('162.00'),
                'created_by': owner_user,
                'approval_status': 'APPROVED',
                'approved_by': owner_user,
                'approved_at': current_date,
                'notes': 'NOC circular dated 2083-07-16',
            }
        )
        self.stdout.write(self.style.SUCCESS("  + Fuel Prices: Current and historical revisions seeded."))
        self.stdout.write(self.style.SUCCESS("\nPhase 2 Station setup initialized successfully!"))
