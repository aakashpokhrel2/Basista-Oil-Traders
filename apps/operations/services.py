"""
Core business logic and transactional services for fuel sales, meter reading logs,
stock ledger updates, and shift cash reconciliation.
Enforces database-level locking and atomic rollbacks.
"""

from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.station.models import StorageTank, Nozzle, FuelType, FuelPrice
from apps.operations.models import Shift, MeterReading, FuelSale, StockMovement
from common.date_utils import ad_to_bs, get_current_bs_date


@transaction.atomic
def record_stock_movement(
    tank: StorageTank,
    movement_type: str,
    quantity: Decimal,
    performed_by,
    direction: str = None,
    shift: Shift = None,
    reference_type: str = '',
    reference_id: str = '',
    remarks: str = ''
) -> StockMovement:
    """
    Safely modify tank stock and record an immutable ledger entry in one atomic transaction.
    Uses select_for_update() row-locking to prevent concurrent race conditions.
    """
    if quantity <= Decimal('0.00'):
        raise ValidationError(_("Movement quantity must be greater than zero."))

    # Determine direction based on movement type if not explicitly passed
    out_types = {'SALE_METER', 'SALE_MANUAL', 'TRANSFER_OUT', 'ADJUSTMENT_LOSS'}
    in_types = {'OPENING', 'PURCHASE', 'SALE_REVERSAL', 'TRANSFER_IN', 'TEST_RETURN', 'ADJUSTMENT_GAIN'}

    if direction is None:
        if movement_type in out_types:
            direction = 'OUT'
        elif movement_type in in_types:
            direction = 'IN'
        else:
            raise ValidationError(f"Unknown movement type: {movement_type}")

    # Row-lock tank instance to prevent concurrency issues
    locked_tank = StorageTank.objects.select_for_update().get(pk=tank.pk)
    opening_bal = locked_tank.current_stock

    if direction == 'OUT':
        if locked_tank.current_stock < quantity:
            raise ValidationError(
                _("Insufficient stock in tank %(tank)s! Cannot deduct %(qty)s L when current balance is only %(cur)s L.") % {
                    'tank': locked_tank.tank_number,
                    'qty': quantity,
                    'cur': locked_tank.current_stock
                }
            )
        new_balance = locked_tank.current_stock - quantity
    else:  # IN
        if (locked_tank.current_stock + quantity) > locked_tank.capacity_liters:
            raise ValidationError(
                _("Capacity overflow! Adding %(qty)s L exceeds tank %(tank)s maximum capacity of %(cap)s L (current: %(cur)s L).") % {
                    'qty': quantity,
                    'tank': locked_tank.tank_number,
                    'cap': locked_tank.capacity_liters,
                    'cur': locked_tank.current_stock
                }
            )
        new_balance = locked_tank.current_stock + quantity

    # Update tank stock
    locked_tank.current_stock = new_balance
    locked_tank.save(update_fields=['current_stock', 'updated_at'])

    # Record auditable movement ledger entry
    movement = StockMovement.objects.create(
        tank=locked_tank,
        movement_type=movement_type,
        direction=direction,
        quantity=quantity,
        opening_balance=opening_bal,
        closing_balance=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        shift=shift,
        performed_by=performed_by,
        timestamp=timezone.now(),
        remarks=remarks,
    )

    if movement_type in ('ADJUSTMENT_LOSS', 'ADJUSTMENT_GAIN', 'TEST_RETURN'):
        try:
            from apps.audit.services import record_audit_event
            record_audit_event(
                action='STOCK_ADJUSTMENT',
                model_name='StorageTank',
                record_id=locked_tank.tank_number,
                user=performed_by,
                previous_value={'current_stock': float(opening_bal)},
                updated_value={'current_stock': float(new_balance), 'adjusted_quantity': float(quantity)},
                reason=remarks or f"Stock adjustment: {movement_type}"
            )
        except Exception:
            pass

    return movement


def generate_invoice_number() -> str:
    """
    Generate sequential invoice number: INV-<BS_YEAR>-<5_DIGIT_SEQUENCE>.
    Example: INV-2083-00001
    """
    bs_today = get_current_bs_date()
    year = bs_today.year if bs_today else timezone.now().year
    prefix = f"INV-{year}-"

    last_sale = FuelSale.objects.filter(invoice_number__startswith=prefix).order_by('-invoice_number').first()
    if last_sale:
        try:
            seq_part = last_sale.invoice_number.split('-')[-1]
            next_seq = int(seq_part) + 1
        except Exception:
            next_seq = FuelSale.objects.count() + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:05d}"


@transaction.atomic
def record_manual_sale(
    shift: Shift,
    fuel_type: FuelType,
    tank: StorageTank,
    quantity: Decimal,
    unit_price: Decimal,
    payment_method: str,
    recorded_by,
    reason_for_manual: str,
    customer_name: str = '',
    vehicle_number: str = '',
    authorized_by = None,
    nozzle: Nozzle = None,
) -> FuelSale:
    """
    Record manual fuel sales entry with strict inventory deduction and audit trail.
    """
    if not reason_for_manual or not reason_for_manual.strip():
        raise ValidationError(_("A documented reason is mandatory when recording manual sales."))

    if quantity <= Decimal('0.00'):
        raise ValidationError(_("Sale quantity must be positive."))

    if unit_price <= Decimal('0.00'):
        raise ValidationError(_("Unit price must be positive."))

    # Validate tank fuel compatibility
    if tank.fuel_type != fuel_type:
        raise ValidationError(_("Selected tank does not contain %(fuel)s.") % {'fuel': fuel_type.name_en})

    total_amount = (quantity * unit_price).quantize(Decimal('0.01'))
    inv_num = generate_invoice_number()

    # 1. Deduct fuel from storage tank
    record_stock_movement(
        tank=tank,
        movement_type='SALE_MANUAL',
        quantity=quantity,
        performed_by=recorded_by,
        direction='OUT',
        shift=shift,
        reference_type='FuelSale',
        reference_id=inv_num,
        remarks=f"Manual sale: {reason_for_manual}"
    )

    # 2. Create Sale Record
    sale = FuelSale.objects.create(
        invoice_number=inv_num,
        shift=shift,
        sale_type='MANUAL',
        fuel_type=fuel_type,
        nozzle=nozzle,
        tank=tank,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        payment_method=payment_method,
        customer_name=customer_name or 'Walk-in Customer / खुद्रा ग्राहक',
        vehicle_number=vehicle_number,
        reason_for_manual=reason_for_manual,
        recorded_by=recorded_by,
        authorized_by=authorized_by or recorded_by,
        transaction_date=timezone.now(),
    )
    return sale


@transaction.atomic
def cancel_fuel_sale(
    sale: FuelSale,
    cancelled_by,
    cancellation_reason: str
) -> FuelSale:
    """
    Void a fuel sale transaction and generate an inverse stock movement to restore inventory.
    Preserves the original transaction record for tax and audit compliance.
    """
    if sale.is_cancelled:
        raise ValidationError(_("This sales transaction is already voided/cancelled."))

    if not cancellation_reason or not cancellation_reason.strip():
        raise ValidationError(_("A documented cancellation reason is required."))

    # 1. Reverse stock into tank
    record_stock_movement(
        tank=sale.tank,
        movement_type='SALE_REVERSAL',
        quantity=sale.quantity,
        performed_by=cancelled_by,
        direction='IN',
        shift=sale.shift,
        reference_type='FuelSaleReversal',
        reference_id=sale.invoice_number,
        remarks=f"Voided sale {sale.invoice_number}: {cancellation_reason}"
    )

    # 2. Update sale record status
    sale.is_cancelled = True
    sale.cancellation_reason = cancellation_reason
    sale.cancelled_by = cancelled_by
    sale.cancelled_at = timezone.now()
    sale.save(update_fields=['is_cancelled', 'cancellation_reason', 'cancelled_by', 'cancelled_at'])

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action='CANCEL',
            model_name='FuelSale',
            record_id=sale.invoice_number,
            user=cancelled_by,
            previous_value={'is_cancelled': False, 'quantity': float(sale.quantity), 'total_amount': float(sale.total_amount)},
            updated_value={'is_cancelled': True, 'restored_litres': float(sale.quantity)},
            reason=cancellation_reason
        )
    except Exception:
        pass

    return sale


@transaction.atomic
def process_meter_reading(
    shift: Shift,
    nozzle: Nozzle,
    closing_reading: Decimal,
    recorded_by,
    test_dispense_quantity: Decimal = Decimal('0.00'),
    is_rollover: bool = False,
    rollover_reason: str = '',
    rollover_authorized_by = None,
    payment_method: str = 'CASH'
) -> tuple[MeterReading, FuelSale]:
    """
    Record shift closing meter reading, auto-calculate dispensed quantity and revenue,
    update nozzle cumulative totalizer, deduct fuel from tank, and generate sales record.
    """
    # 1. Lock nozzle and get latest opening reading
    locked_nozzle = Nozzle.objects.select_for_update().get(pk=nozzle.pk)
    opening_reading = locked_nozzle.current_meter_reading

    # 2. Get active price for nozzle fuel type
    fuel = locked_nozzle.fuel_type
    effective_price = fuel.get_current_price()
    if not effective_price:
        raise ValidationError(_("No active selling price found for %(fuel)s.") % {'fuel': fuel.name_en})
    unit_price = effective_price.selling_price

    if MeterReading.objects.filter(shift=shift, nozzle=locked_nozzle).exists():
        raise ValidationError(
            _("Nozzle '%(nozzle)s' already has a recorded closing reading for Shift %(shift)s.") % {
                'nozzle': locked_nozzle.nozzle_code,
                'shift': shift.shift_number
            }
        )

    # 3. Create MeterReading instance (clean() calculates quantity_sold, net_quantity, total)
    reading = MeterReading(
        nozzle=locked_nozzle,
        shift=shift,
        opening_meter_reading=opening_reading,
        closing_meter_reading=closing_reading,
        test_dispense_quantity=test_dispense_quantity,
        unit_price=unit_price,
        reading_timestamp=timezone.now(),
        recorded_by=recorded_by,
        is_rollover=is_rollover,
        rollover_reason=rollover_reason,
        rollover_authorized_by=rollover_authorized_by,
    )
    reading.clean()
    reading.save()

    # 4. Update nozzle current meter reading
    locked_nozzle.current_meter_reading = closing_reading
    locked_nozzle.save(update_fields=['current_meter_reading'])

    sale = None
    # 5. If net fuel was sold, deduct gross dispensed from tank and create FuelSale record
    if reading.net_quantity_sold > Decimal('0.00'):
        inv_num = generate_invoice_number()

        record_stock_movement(
            tank=locked_nozzle.tank,
            movement_type='SALE_METER',
            quantity=reading.quantity_sold,
            performed_by=recorded_by,
            direction='OUT',
            shift=shift,
            reference_type='MeterReading',
            reference_id=str(reading.pk),
            remarks=f"Meter sale via {locked_nozzle.nozzle_code} (Shift {shift.shift_number})"
        )

        sale = FuelSale.objects.create(
            invoice_number=inv_num,
            shift=shift,
            sale_type='METER',
            fuel_type=fuel,
            nozzle=locked_nozzle,
            tank=locked_nozzle.tank,
            quantity=reading.net_quantity_sold,
            unit_price=unit_price,
            total_amount=reading.total_amount,
            payment_method=payment_method,
            customer_name=_('Shift Dispensed Total / सिफ्ट बिक्री'),
            recorded_by=recorded_by,
            transaction_date=timezone.now(),
        )

    # 6. If test calibration dispense occurred, record test return to tank
    if test_dispense_quantity > Decimal('0.00'):
        record_stock_movement(
            tank=locked_nozzle.tank,
            movement_type='TEST_RETURN',
            quantity=test_dispense_quantity,
            performed_by=recorded_by,
            direction='IN',
            shift=shift,
            reference_type='CalibrationTest',
            reference_id=str(reading.pk),
            remarks=f"Calibration return from {locked_nozzle.nozzle_code}"
        )

    if is_rollover:
        try:
            from apps.audit.services import record_audit_event
            record_audit_event(
                action='METER_ROLLOVER',
                model_name='Nozzle',
                record_id=locked_nozzle.nozzle_code,
                user=rollover_authorized_by or recorded_by,
                previous_value={'opening_reading': float(opening_reading)},
                updated_value={'closing_reading': float(closing_reading)},
                reason=rollover_reason or 'Authorized meter counter rollover'
            )
        except Exception:
            pass

    return reading, sale


@transaction.atomic
def close_shift_session(
    shift: Shift,
    closing_cash_counted: Decimal,
    actual_cash_collected: Decimal,
    handover_notes: str = ''
) -> Shift:
    """
    Close an active shift, calculate cash fuel sales, compute cash shortage/excess,
    and update shift status to CLOSED pending manager reconciliation approval.
    """
    if shift.status != 'OPEN':
        raise ValidationError(_("This shift is already closed."))

    # Aggregate active sales belonging to this shift
    shift_sales = shift.sales.filter(is_cancelled=False)
    cash_sales_total = shift_sales.filter(payment_method='CASH').aggregate(
        total=models.Sum('total_amount')
    )['total'] or Decimal('0.00')

    # Expected cash = Opening cash + Cash sales
    expected_cash = shift.opening_cash_balance + cash_sales_total
    cash_variance = closing_cash_counted - expected_cash

    shift.closing_time = timezone.now()
    shift.closing_cash_balance = closing_cash_counted
    shift.actual_cash_collected = actual_cash_collected
    shift.expected_cash_balance = expected_cash
    shift.cash_difference = cash_variance
    shift.handover_notes = handover_notes
    shift.status = 'CLOSED'
    shift.save()

    return shift
