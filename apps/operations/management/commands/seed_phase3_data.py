import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.station.models import FuelType, StorageTank, Pump, Nozzle, FuelPrice
from apps.operations.models import ShiftSchedule, Shift, MeterReading, FuelSale, StockMovement
from apps.operations.services import (
    process_meter_reading,
    record_manual_sale,
    close_shift_session,
    record_stock_movement
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic sample operations data for Phase 3 (Shifts, Readings, Sales, Ledger)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Phase 3 operations data..."))

        # 1. Retrieve users
        owner = User.objects.filter(role='OWNER').first() or User.objects.filter(is_superuser=True).first()
        manager = User.objects.filter(role='MANAGER').first() or owner
        cashier = User.objects.filter(role='CASHIER').first() or owner
        operator = User.objects.filter(role='PUMP_OPERATOR').first() or cashier

        if not owner:
            self.stdout.write(self.style.ERROR("No users found. Please create or seed users first."))
            return

        # 2. Check station configuration
        ms = FuelType.objects.filter(code='MS').first()
        hsd = FuelType.objects.filter(code='HSD').first()
        if not ms or not hsd:
            self.stdout.write(self.style.ERROR("Fuel types MS and HSD not found. Run seed_station_data first."))
            return

        tank_ms = StorageTank.objects.filter(fuel_type=ms).first()
        tank_hsd = StorageTank.objects.filter(fuel_type=hsd).first()
        if not tank_ms or not tank_hsd:
            self.stdout.write(self.style.ERROR("Tanks not found. Run seed_station_data first."))
            return

        # Ensure initial stock in tanks
        if tank_ms.current_stock < Decimal('5000.00'):
            record_stock_movement(
                tank=tank_ms,
                movement_type='PURCHASE',
                quantity=Decimal('8000.00'),
                performed_by=owner,
                reference_type='SeedPurchase',
                reference_id='PO-2026-001',
                remarks='Initial tanker purchase receipt from NOC Amlekhgunj depot'
            )
        if tank_hsd.current_stock < Decimal('5000.00'):
            record_stock_movement(
                tank=tank_hsd,
                movement_type='PURCHASE',
                quantity=Decimal('12000.00'),
                performed_by=owner,
                reference_type='SeedPurchase',
                reference_id='PO-2026-002',
                remarks='Initial tanker purchase receipt from NOC Birgunj depot'
            )

        # 3. Retrieve or create schedules
        day_sched, _ = ShiftSchedule.objects.get_or_create(
            name_en="Morning Shift",
            defaults={
                'name_ne': "बिहानी सिफ्ट",
                'start_time': datetime.time(6, 0),
                'end_time': datetime.time(14, 0),
                'is_active': True,
            }
        )
        eve_sched, _ = ShiftSchedule.objects.get_or_create(
            name_en="Day/Evening Shift",
            defaults={
                'name_ne': "दिउँसो/साँझ सिफ्ट",
                'start_time': datetime.time(14, 0),
                'end_time': datetime.time(22, 0),
                'is_active': True,
            }
        )

        # 4. Check if we already have shifts
        if Shift.objects.filter(shift_number="SFT-2026-00001").exists():
            self.stdout.write(self.style.SUCCESS("Phase 3 seed data already exists. Skipping."))
            return

        # 5. Create Shift 1 (Completed & Approved historical shift)
        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)

        shift1 = Shift.objects.create(
            shift_number="SFT-2026-00001",
            schedule=day_sched,
            date_ad=yesterday,
            supervisor=manager,
            opening_cash_balance=Decimal('5000.00'),
            handover_notes="Morning opening float verified by manager",
            status='OPEN'
        )
        shift1.operators.add(cashier, operator)

        # Record meter readings for nozzles in Shift 1
        nozzles = list(Nozzle.objects.filter(status='ACTIVE'))
        if len(nozzles) >= 2:
            n1 = nozzles[0] # e.g. P1-N1 (Petrol)
            n2 = nozzles[1] # e.g. P1-N2 (Diesel)

            # Record reading for n1: 150 Litres
            close_n1 = n1.current_meter_reading + Decimal('150.00')
            process_meter_reading(
                shift=shift1,
                nozzle=n1,
                closing_reading=close_n1,
                recorded_by=operator,
                test_dispense_quantity=Decimal('2.00'),
            )

            # Record reading for n2: 220 Litres
            close_n2 = n2.current_meter_reading + Decimal('220.00')
            process_meter_reading(
                shift=shift1,
                nozzle=n2,
                closing_reading=close_n2,
                recorded_by=operator,
                test_dispense_quantity=Decimal('0.00'),
            )

        # Record a manual retail sale during Shift 1
        record_manual_sale(
            shift=shift1,
            fuel_type=ms,
            tank=tank_ms,
            quantity=Decimal('30.00'),
            unit_price=Decimal('175.00'),
            payment_method='CASH',
            recorded_by=cashier,
            reason_for_manual="Direct drum filling for construction generator; dispenser nozzle auto-stop sensor issue.",
            customer_name="Everest Highway Builders",
            vehicle_number="Ba 2 Ka 4512",
            authorized_by=manager
        )

        # Close Shift 1
        shift1_sales_total = shift1.sales.filter(is_cancelled=False).values_list('total_amount', flat=True)
        tot_calc = sum(shift1_sales_total, Decimal('0.00')) + Decimal('5000.00') # opening cash

        close_shift_session(
            shift=shift1,
            closing_cash_counted=tot_calc,
            actual_cash_collected=tot_calc,
            handover_notes="Morning shift accounts verified and balanced perfectly."
        )
        shift1.status = 'APPROVED'
        shift1.approved_by = owner
        shift1.approved_at = timezone.now()
        shift1.save()

        # 6. Create Shift 2 (Currently OPEN for today)
        shift2 = Shift.objects.create(
            shift_number="SFT-2026-00002",
            schedule=eve_sched,
            date_ad=today,
            supervisor=manager,
            opening_cash_balance=Decimal('6000.00'),
            handover_notes="Opening cash float Rs 6,000 handed to cashier for today's active shift.",
            status='OPEN'
        )
        shift2.operators.add(cashier, operator)

        # Record 1 active manual sale in Shift 2
        record_manual_sale(
            shift=shift2,
            fuel_type=hsd,
            tank=tank_hsd,
            quantity=Decimal('50.00'),
            unit_price=Decimal('155.00'),
            payment_method='CREDIT',
            recorded_by=cashier,
            reason_for_manual="Authorized corporate credit fuel supply for Bagmati Transport.",
            customer_name="Bagmati Transport Pvt Ltd",
            vehicle_number="Na 5 Kha 9821",
            authorized_by=manager
        )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded Phase 3 data:\n"
            f"  - Completed Shift: {shift1.shift_number} (Approved with meter & manual sales)\n"
            f"  - Active OPEN Shift: {shift2.shift_number} (Ready for user testing)\n"
            f"  - Double-entry stock ledger updated for MS and HSD tanks.\n"
        ))
