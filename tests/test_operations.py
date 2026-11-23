"""
Comprehensive automated tests for Phase 3: Fuel Operations, Shift Management,
Meter Readings, Manual Sales, Auditable Stock Ledger, and Cash Reconciliation.
"""

import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.station.models import FuelType, StorageTank, Pump, Nozzle, FuelPrice
from apps.operations.models import ShiftSchedule, Shift, MeterReading, FuelSale, StockMovement
from apps.operations.services import (
    record_stock_movement,
    generate_invoice_number,
    record_manual_sale,
    cancel_fuel_sale,
    process_meter_reading,
    close_shift_session,
)

User = get_user_model()


class FuelOperationsTestCase(TestCase):
    """Test suite for Phase 3 Fuel Operations module."""

    def setUp(self):
        # 1. Create Users across roles
        self.owner = User.objects.create_user(
            username='owner_test',
            email='owner@petrolstation.np',
            password='Password123!',
            role='OWNER',
            phone_number='9800000001'
        )
        self.manager = User.objects.create_user(
            username='manager_test',
            email='manager@petrolstation.np',
            password='Password123!',
            role='MANAGER',
            phone_number='9800000002'
        )
        self.cashier = User.objects.create_user(
            username='cashier_test',
            email='cashier@petrolstation.np',
            password='Password123!',
            role='CASHIER',
            phone_number='9800000003'
        )
        self.operator = User.objects.create_user(
            username='operator_test',
            email='operator@petrolstation.np',
            password='Password123!',
            role='PUMP_OPERATOR',
            phone_number='9800000004'
        )

        # 2. Fuel Types
        self.ms, _ = FuelType.objects.get_or_create(
            code='MS',
            defaults={'name_en': 'Petrol (MS)', 'name_ne': 'पेट्रोल', 'unit': 'Litres', 'is_active': True}
        )
        self.hsd, _ = FuelType.objects.get_or_create(
            code='HSD',
            defaults={'name_en': 'Diesel (HSD)', 'name_ne': 'डिजेल', 'unit': 'Litres', 'is_active': True}
        )

        # 3. Fuel Prices
        self.price_ms = FuelPrice.objects.create(
            fuel_type=self.ms,
            purchase_price=Decimal('160.00'),
            selling_price=Decimal('175.00'),
            effective_date=timezone.now() - datetime.timedelta(days=2),
            approval_status='APPROVED',
            created_by=self.owner
        )
        self.price_hsd = FuelPrice.objects.create(
            fuel_type=self.hsd,
            purchase_price=Decimal('140.00'),
            selling_price=Decimal('155.00'),
            effective_date=timezone.now() - datetime.timedelta(days=2),
            approval_status='APPROVED',
            created_by=self.owner
        )

        # 4. Storage Tanks
        self.tank_ms = StorageTank.objects.create(
            tank_number='T-MS-01',
            tank_name='Underground MS Tank 1',
            fuel_type=self.ms,
            capacity_liters=Decimal('20000.00'),
            current_stock=Decimal('10000.00'),
            is_active=True
        )
        self.tank_hsd = StorageTank.objects.create(
            tank_number='T-HSD-01',
            tank_name='Underground HSD Tank 1',
            fuel_type=self.hsd,
            capacity_liters=Decimal('25000.00'),
            current_stock=Decimal('15000.00'),
            is_active=True
        )

        # 5. Pump & Nozzles
        self.pump1 = Pump.objects.create(
            pump_number=1,
            pump_name='Dispenser Island 1',
            status='ACTIVE'
        )
        self.nozzle1_ms = Nozzle.objects.create(
            pump=self.pump1,
            nozzle_number=1,
            nozzle_code='P1-N1',
            fuel_type=self.ms,
            tank=self.tank_ms,
            current_meter_reading=Decimal('1000.00'),
            status='ACTIVE'
        )
        self.nozzle2_hsd = Nozzle.objects.create(
            pump=self.pump1,
            nozzle_number=2,
            nozzle_code='P1-N2',
            fuel_type=self.hsd,
            tank=self.tank_hsd,
            current_meter_reading=Decimal('500.00'),
            status='ACTIVE'
        )

        # 6. Shift Schedule & Active Shift
        self.schedule, _ = ShiftSchedule.objects.get_or_create(
            name_en="Morning Shift",
            defaults={
                'name_ne': "बिहानी सिफ्ट",
                'start_time': datetime.time(6, 0),
                'end_time': datetime.time(14, 0),
                'is_active': True,
            }
        )
        self.shift = Shift.objects.create(
            shift_number='SFT-TEST-0001',
            schedule=self.schedule,
            date_ad=timezone.now().date(),
            supervisor=self.manager,
            opening_cash_balance=Decimal('5000.00'),
            status='OPEN'
        )
        self.shift.operators.add(self.cashier, self.operator)

    # --------------------------------------------------------------------------
    # 1. Meter Reading Calculations & Validations
    # --------------------------------------------------------------------------

    def test_meter_reading_calculation_and_stock_deduction(self):
        """
        Verify meter calculation:
        Gross Dispensed = Closing (1200) - Opening (1000) = 200 L
        Net Sold = Gross (200) - Testing (5) = 195 L
        Total Amount = 195 * 175 = NPR 34,125.00
        Underground Tank stock should be reduced by 195 L and testing 5 L returned.
        """
        initial_tank_stock = self.tank_ms.current_stock
        closing_meter = Decimal('1200.00')
        testing_qty = Decimal('5.00')

        reading, sale = process_meter_reading(
            shift=self.shift,
            nozzle=self.nozzle1_ms,
            closing_reading=closing_meter,
            recorded_by=self.operator,
            test_dispense_quantity=testing_qty,
            payment_method='CASH'
        )

        # Verify Meter Reading Record
        self.assertEqual(reading.opening_meter_reading, Decimal('1000.00'))
        self.assertEqual(reading.closing_meter_reading, Decimal('1200.00'))
        self.assertEqual(reading.quantity_sold, Decimal('200.00'))
        self.assertEqual(reading.test_dispense_quantity, Decimal('5.00'))
        self.assertEqual(reading.net_quantity_sold, Decimal('195.00'))
        self.assertEqual(reading.unit_price, Decimal('175.00'))
        self.assertEqual(reading.total_amount, Decimal('34125.00'))

        # Verify Nozzle cumulative meter updated
        self.nozzle1_ms.refresh_from_db()
        self.assertEqual(self.nozzle1_ms.current_meter_reading, Decimal('1200.00'))

        # Verify Sale Record Generated
        self.assertIsNotNone(sale)
        self.assertEqual(sale.quantity, Decimal('195.00'))
        self.assertEqual(sale.total_amount, Decimal('34125.00'))
        self.assertEqual(sale.sale_type, 'METER')

        # Verify Tank Stock Deducted (10000 - 195 = 9805)
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, initial_tank_stock - Decimal('195.00'))

    def test_negative_meter_reading_rejected(self):
        """Closing reading less than opening reading without rollover must raise ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            process_meter_reading(
                shift=self.shift,
                nozzle=self.nozzle1_ms,
                closing_reading=Decimal('950.00'),  # Opening is 1000.00
                recorded_by=self.operator,
                is_rollover=False
            )
        self.assertIn("cannot be less than", str(ctx.exception))

    def test_meter_rollover_with_authorization(self):
        """Authorized meter rollover calculation (max 99999.99 totalizer cycle)."""
        self.tank_ms.capacity_liters = Decimal('200000.00')
        self.tank_ms.current_stock = Decimal('150000.00')
        self.tank_ms.save()

        reading, sale = process_meter_reading(
            shift=self.shift,
            nozzle=self.nozzle1_ms,
            closing_reading=Decimal('50.00'),  # Rolled over past 99999.99
            recorded_by=self.operator,
            is_rollover=True,
            rollover_reason="Totalizer 99,999.99 rollover after manufacturer cycle",
            rollover_authorized_by=self.manager
        )
        # Expected dispensed: (99999.99 - 1000.00) + 50.00 = 99049.99
        expected_dispensed = (Decimal('99999.99') - Decimal('1000.00')) + Decimal('50.00')
        self.assertEqual(reading.quantity_sold, expected_dispensed)
        self.assertTrue(reading.is_rollover)

    def test_duplicate_meter_reading_in_same_shift_rejected(self):
        """Cannot log meter reading twice for the same nozzle in the same shift."""
        process_meter_reading(
            shift=self.shift,
            nozzle=self.nozzle1_ms,
            closing_reading=Decimal('1050.00'),
            recorded_by=self.operator
        )
        with self.assertRaises(ValidationError) as ctx:
            process_meter_reading(
                shift=self.shift,
                nozzle=self.nozzle1_ms,
                closing_reading=Decimal('1100.00'),
                recorded_by=self.operator
            )
        self.assertIn("already has a recorded closing reading", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 2. Manual Sales Entry & Stock Integrity
    # --------------------------------------------------------------------------

    def test_manual_sale_success_and_stock_ledger(self):
        """Manual fuel sale records invoice, updates tank balance, and writes to audit ledger."""
        initial_tank_stock = self.tank_ms.current_stock

        sale = record_manual_sale(
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            quantity=Decimal('40.00'),
            unit_price=Decimal('175.00'),
            payment_method='CASH',
            recorded_by=self.cashier,
            reason_for_manual="Emergency generator supply during grid power cut",
            customer_name="Annapurna Hotel",
            vehicle_number="Ba 1 Ka 1234",
            authorized_by=self.manager
        )

        self.assertEqual(sale.total_amount, Decimal('7000.00'))
        self.assertEqual(sale.sale_type, 'MANUAL')
        self.assertTrue(sale.invoice_number.startswith('INV-'))

        # Tank stock deducted
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, initial_tank_stock - Decimal('40.00'))

        # Audit ledger record created
        ledger_entry = StockMovement.objects.filter(reference_id=sale.invoice_number).first()
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.movement_type, 'SALE_MANUAL')
        self.assertEqual(ledger_entry.direction, 'OUT')
        self.assertEqual(ledger_entry.quantity, Decimal('40.00'))

    def test_manual_sale_requires_reason(self):
        """Manual fuel sale without documented reason must fail validation."""
        with self.assertRaises(ValidationError):
            record_manual_sale(
                shift=self.shift,
                fuel_type=self.ms,
                tank=self.tank_ms,
                quantity=Decimal('20.00'),
                unit_price=Decimal('175.00'),
                payment_method='CASH',
                recorded_by=self.cashier,
                reason_for_manual=""  # Empty reason
            )

    def test_insufficient_stock_rollback(self):
        """Attempting to sell more fuel than current tank balance raises ValidationError."""
        self.tank_ms.current_stock = Decimal('50.00')
        self.tank_ms.save()

        with self.assertRaises(ValidationError) as ctx:
            record_manual_sale(
                shift=self.shift,
                fuel_type=self.ms,
                tank=self.tank_ms,
                quantity=Decimal('100.00'),  # Only 50 L available
                unit_price=Decimal('175.00'),
                payment_method='CASH',
                recorded_by=self.cashier,
                reason_for_manual="Test insufficient"
            )
        self.assertIn("Insufficient stock", str(ctx.exception))

        # Tank stock remains untouched
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, Decimal('50.00'))

    # --------------------------------------------------------------------------
    # 3. Sales Cancellation & Double-Entry Reversal
    # --------------------------------------------------------------------------

    def test_sales_cancellation_and_inventory_reversal(self):
        """
        Voiding a sale marks the transaction as cancelled and posts an inverse
        StockMovement (SALE_REVERSAL) restoring the exact fuel volume into the tank.
        """
        initial_tank_stock = self.tank_ms.current_stock

        sale = record_manual_sale(
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            quantity=Decimal('60.00'),
            unit_price=Decimal('175.00'),
            payment_method='CASH',
            recorded_by=self.cashier,
            reason_for_manual="Customer requested drum dispense"
        )
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, initial_tank_stock - Decimal('60.00'))

        # Cancel the sale
        cancel_fuel_sale(
            sale=sale,
            cancelled_by=self.manager,
            cancellation_reason="Wrong vehicle entered; customer paid with different account."
        )

        sale.refresh_from_db()
        self.assertTrue(sale.is_cancelled)
        self.assertEqual(sale.cancelled_by, self.manager)
        self.assertIn("Wrong vehicle", sale.cancellation_reason)

        # Tank stock restored back to initial balance
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, initial_tank_stock)

        # Audit ledger contains SALE_REVERSAL entry
        reversal_entry = StockMovement.objects.filter(
            movement_type='SALE_REVERSAL',
            reference_id=sale.invoice_number
        ).first()
        self.assertIsNotNone(reversal_entry)
        self.assertEqual(reversal_entry.direction, 'IN')
        self.assertEqual(reversal_entry.quantity, Decimal('60.00'))

    def test_cannot_cancel_already_cancelled_sale(self):
        """Attempting to cancel an already cancelled invoice raises ValidationError."""
        sale = record_manual_sale(
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            quantity=Decimal('10.00'),
            unit_price=Decimal('175.00'),
            payment_method='CASH',
            recorded_by=self.cashier,
            reason_for_manual="Test cancel twice"
        )
        cancel_fuel_sale(sale=sale, cancelled_by=self.manager, cancellation_reason="First cancel")

        with self.assertRaises(ValidationError):
            cancel_fuel_sale(sale=sale, cancelled_by=self.manager, cancellation_reason="Second cancel")

    # --------------------------------------------------------------------------
    # 4. Shift Closing & Cash Reconciliation
    # --------------------------------------------------------------------------

    def test_shift_closing_and_cash_variance(self):
        """
        Verify shift closure:
        Opening Cash = 5,000.00
        Cash Sale 1 = 3,500.00
        Credit Sale = 2,000.00 (not included in cash drawer)
        Expected Cash = 5,000 + 3,500 = 8,500.00
        Actual Cash Counted = 8,700.00 (Overage of +200.00)
        """
        # Cash Sale: 20 L @ 175 = 3500.00
        record_manual_sale(
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            quantity=Decimal('20.00'),
            unit_price=Decimal('175.00'),
            payment_method='CASH',
            recorded_by=self.cashier,
            reason_for_manual="Retail Cash"
        )
        # Credit Sale: 10 L @ 175 = 1750.00
        record_manual_sale(
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            quantity=Decimal('10.00'),
            unit_price=Decimal('175.00'),
            payment_method='CREDIT',
            recorded_by=self.cashier,
            reason_for_manual="Corporate Credit"
        )

        counted_cash = Decimal('8700.00')
        closed_shift = close_shift_session(
            shift=self.shift,
            closing_cash_counted=counted_cash,
            actual_cash_collected=counted_cash,
            handover_notes="Cash counted in safe; Rs 200 excess tip/roundoff."
        )

        self.assertEqual(closed_shift.status, 'CLOSED')
        self.assertEqual(closed_shift.expected_cash_balance, Decimal('8500.00'))
        self.assertEqual(closed_shift.closing_cash_balance, Decimal('8700.00'))
        self.assertEqual(closed_shift.cash_difference, Decimal('200.00'))

    def test_cannot_close_already_closed_shift(self):
        """Closing a shift that is already closed raises ValidationError."""
        close_shift_session(
            shift=self.shift,
            closing_cash_counted=Decimal('5000.00'),
            actual_cash_collected=Decimal('5000.00')
        )
        with self.assertRaises(ValidationError):
            close_shift_session(
                shift=self.shift,
                closing_cash_counted=Decimal('5000.00'),
                actual_cash_collected=Decimal('5000.00')
            )

    # --------------------------------------------------------------------------
    # 5. Stock Adjustment (Dip Loss & Calibration Return)
    # --------------------------------------------------------------------------

    def test_stock_adjustment_evaporation_loss(self):
        """Stock adjustment for evaporation / dip loss reduces tank balance and logs ledger."""
        initial_stock = self.tank_ms.current_stock
        loss_qty = Decimal('25.50')

        movement = record_stock_movement(
            tank=self.tank_ms,
            movement_type='ADJUSTMENT_LOSS',
            quantity=loss_qty,
            performed_by=self.manager,
            reference_type='ManualAdjustment',
            remarks='Daily dip variation evaporation loss verified'
        )

        self.assertEqual(movement.direction, 'OUT')
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, initial_stock - loss_qty)
        self.assertEqual(movement.closing_balance, initial_stock - loss_qty)

    # --------------------------------------------------------------------------
    # 6. HTTP Views & Bilingual Template Responses
    # --------------------------------------------------------------------------

    def test_daily_sales_register_view(self):
        """Manager can access sales register and view invoices."""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('operations:sales_register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'operations/sales_register.html')

    def test_sale_detail_view(self):
        """Viewing a sale detail page renders tax invoice."""
        sale = record_manual_sale(
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            quantity=Decimal('15.00'),
            unit_price=Decimal('175.00'),
            payment_method='CASH',
            recorded_by=self.cashier,
            reason_for_manual="Customer bill print test"
        )
        self.client.force_login(self.cashier)
        response = self.client.get(reverse('operations:sale_detail', kwargs={'pk': sale.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, sale.invoice_number)
        self.assertContains(response, 'Tax Invoice')

    def test_stock_ledger_view(self):
        """Accountant can view auditable stock movement ledger."""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('operations:stock_ledger'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'operations/stock_ledger.html')

    def test_sales_reconciliation_view(self):
        """Manager can view multi-dimensional sales reconciliation report."""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('operations:sales_reconciliation'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'operations/sales_reconciliation.html')
        self.assertIn('overall', response.context)
        self.assertIn('fuel_breakdown', response.context)
        self.assertIn('nozzle_breakdown', response.context)
