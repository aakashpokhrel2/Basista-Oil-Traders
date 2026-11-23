from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.purchases.models import Supplier, FuelPurchase, SupplierPayment
from apps.accounting.models import Account
from apps.accounting.services import (
    create_journal_entry, record_cash_transaction, get_or_create_default_accounts
)
from apps.operations.services import record_stock_movement
from common.date_utils import get_current_bs_date


def generate_supplier_payment_number() -> str:
    """Generate sequential Supplier Payment Receipt: PAY-YYYY-XXXXX"""
    bs_today = get_current_bs_date()
    year = bs_today.year if bs_today else timezone.now().year
    prefix = f"PAY-{year}-"
    last_pay = SupplierPayment.objects.filter(payment_number__startswith=prefix).order_by('-payment_number').first()
    if last_pay:
        try:
            seq = int(last_pay.payment_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


@transaction.atomic
def approve_fuel_purchase(purchase: FuelPurchase, approved_by) -> FuelPurchase:
    """
    Approve an incoming fuel tanker delivery:
    1. Update status to APPROVED.
    2. Inward delivered fuel into StorageTank and log StockMovement.
    3. Update Supplier outstanding payable balance.
    4. Post double-entry journal entry:
       Debit: Fuel Inventory Asset (1060 MS or 1061 HSD)
       Credit: Accounts Payable - Supplier (2010)
    """
    if purchase.approval_status != 'PENDING':
        raise ValidationError(_("Only purchases in 'PENDING' status can be approved."))

    # 1. Update purchase status
    purchase.approval_status = 'APPROVED'
    purchase.approved_by = approved_by
    purchase.approved_at = timezone.now()
    purchase.save(update_fields=['approval_status', 'approved_by', 'approved_at'])

    # 2. Record inward physical fuel delivery in underground storage tank
    record_stock_movement(
        tank=purchase.receiving_tank,
        movement_type='PURCHASE',
        quantity=purchase.delivered_quantity,
        performed_by=approved_by,
        direction='IN',
        reference_type='FuelPurchase',
        reference_id=purchase.invoice_number,
        remarks=f"Tanker delivery from {purchase.supplier.name} (Tanker: {purchase.tanker_number or 'N/A'}, Invoice: {purchase.invoice_number})"
    )

    # 3. Update Supplier Payable Balance
    supplier = Supplier.objects.select_for_update().get(pk=purchase.supplier.pk)
    supplier.current_balance += purchase.total_amount
    supplier.save(update_fields=['current_balance', 'updated_at'])

    # 4. Post Double-Entry Journal Entry
    get_or_create_default_accounts()
    inventory_code = '1060' if purchase.fuel_type.code == 'MS' else '1061'
    inv_account = Account.objects.get(account_number=inventory_code)
    payable_account = Account.objects.get(account_number='2010')

    create_journal_entry(
        date=purchase.purchase_date,
        description=f"Purchase delivery: {purchase.fuel_type.code} {purchase.delivered_quantity} L from {supplier.name} (Inv #{purchase.invoice_number})",
        lines_data=[
            {'account': inv_account, 'debit': purchase.total_amount, 'credit': Decimal('0.00'), 'description': f"Stock receipt {purchase.fuel_type.code}"},
            {'account': payable_account, 'debit': Decimal('0.00'), 'credit': purchase.total_amount, 'description': f"Payable to {supplier.name}"},
        ],
        created_by=approved_by,
        reference_type='FuelPurchase',
        reference_id=purchase.invoice_number,
    )

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action='APPROVE',
            model_name='FuelPurchase',
            record_id=purchase.invoice_number,
            user=approved_by,
            previous_value={'approval_status': 'PENDING'},
            updated_value={'approval_status': 'APPROVED', 'delivered_quantity': float(purchase.delivered_quantity)},
            reason=f"Approved delivery of {purchase.delivered_quantity}L {purchase.fuel_type.code} to {purchase.receiving_tank.tank_name}"
        )
    except Exception:
        pass

    return purchase


@transaction.atomic
def record_supplier_payment(
    supplier: Supplier,
    amount: Decimal,
    payment_method: str,
    recorded_by,
    purchase: FuelPurchase = None,
    payment_reference: str = '',
    notes: str = '',
    payment_date = None
) -> SupplierPayment:
    """
    Record payment made to supplier:
    1. Creates SupplierPayment record.
    2. Deducts amount from supplier.current_balance.
    3. If cash, records Cash Book outflow.
    4. Posts double-entry:
       Debit: Accounts Payable - Supplier (2010)
       Credit: Cash in Drawer (1010) or Bank (1020)
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError(_("Payment amount must be greater than zero."))

    p_num = generate_supplier_payment_number()
    p_date = payment_date or timezone.now().date()

    payment = SupplierPayment.objects.create(
        payment_number=p_num,
        supplier=supplier,
        purchase=purchase,
        payment_date=p_date,
        amount=amount,
        payment_method=payment_method,
        payment_reference=payment_reference,
        recorded_by=recorded_by,
        notes=notes,
    )
    payment.clean()
    payment.save()

    # Update supplier balance
    locked_supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)
    locked_supplier.current_balance -= amount
    locked_supplier.save(update_fields=['current_balance', 'updated_at'])

    # If linked to specific purchase invoice
    if purchase:
        purchase.paid_amount += amount
        if purchase.paid_amount >= purchase.total_amount:
            purchase.payment_status = 'PAID'
        else:
            purchase.payment_status = 'PARTIAL'
        purchase.save(update_fields=['paid_amount', 'payment_status'])

    # Cash Book entry if paid in cash
    if payment_method == 'CASH':
        record_cash_transaction(
            transaction_type='OUTFLOW',
            source_category='SUPPLIER_PAYMENT',
            amount=amount,
            performed_by=recorded_by,
            description=f"Payment to supplier {supplier.name} (Receipt #{p_num})",
            reference_type='SupplierPayment',
            reference_id=p_num,
            date=p_date
        )

    # Double-entry Journal Entry
    get_or_create_default_accounts()
    payable_account = Account.objects.get(account_number='2010')
    credit_account = Account.objects.get(account_number='1010' if payment_method == 'CASH' else '1020')

    create_journal_entry(
        date=p_date,
        description=f"Supplier payment to {supplier.name} via {payment_method} (Ref: {p_num})",
        lines_data=[
            {'account': payable_account, 'debit': amount, 'credit': Decimal('0.00'), 'description': f"Discharge payable to {supplier.name}"},
            {'account': credit_account, 'debit': Decimal('0.00'), 'credit': amount, 'description': f"Paid via {payment_method}"},
        ],
        created_by=recorded_by,
        reference_type='SupplierPayment',
        reference_id=p_num,
    )

    return payment
