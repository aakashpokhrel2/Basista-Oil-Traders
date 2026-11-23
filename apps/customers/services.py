from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.customers.models import Customer, CustomerPayment
from apps.accounting.models import Account
from apps.accounting.services import (
    create_journal_entry, record_cash_transaction, get_or_create_default_accounts
)
from common.date_utils import get_current_bs_date


def generate_customer_receipt_number() -> str:
    """Generate sequential Customer Receipt Number: CR-YYYY-XXXXX"""
    bs_today = get_current_bs_date()
    year = bs_today.year if bs_today else timezone.now().year
    prefix = f"CR-{year}-"
    last_cr = CustomerPayment.objects.filter(receipt_number__startswith=prefix).order_by('-receipt_number').first()
    if last_cr:
        try:
            seq = int(last_cr.receipt_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


@transaction.atomic
def record_customer_credit_charge(
    customer: Customer,
    amount: Decimal,
    invoice_number: str,
    fuel_code: str,
    recorded_by
):
    """
    Called when a credit sale is recorded:
    1. Validates credit limit.
    2. Increases customer.current_balance.
    3. Posts double-entry:
       Debit: Accounts Receivable (1050)
       Credit: Fuel Sales Revenue (4010 MS or 4020 HSD)
    """
    amount = Decimal(str(amount))
    locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)

    if locked_customer.status != 'ACTIVE':
        raise ValidationError(_("Customer '%(name)s' credit account is %(status)s.") % {
            'name': locked_customer.name,
            'status': locked_customer.get_status_display()
        })

    if (locked_customer.current_balance + amount) > locked_customer.credit_limit:
        raise ValidationError(
            _("Credit limit exceeded! Customer %(name)s current debt is NPR %(cur)s. Adding %(amt)s exceeds limit of NPR %(limit)s.") % {
                'name': locked_customer.name,
                'cur': locked_customer.current_balance,
                'amt': amount,
                'limit': locked_customer.credit_limit
            }
        )

    locked_customer.current_balance += amount
    locked_customer.save(update_fields=['current_balance', 'updated_at'])

    # Post double-entry
    get_or_create_default_accounts()
    ar_account = Account.objects.get(account_number='1050')
    rev_code = '4010' if fuel_code == 'MS' else '4020'
    rev_account = Account.objects.get(account_number=rev_code)

    create_journal_entry(
        date=timezone.now().date(),
        description=f"Credit fuel sale to {locked_customer.name} (Invoice #{invoice_number})",
        lines_data=[
            {'account': ar_account, 'debit': amount, 'credit': Decimal('0.00'), 'description': f"Receivable from {locked_customer.name}"},
            {'account': rev_account, 'debit': Decimal('0.00'), 'credit': amount, 'description': f"Fuel sales revenue ({fuel_code})"},
        ],
        created_by=recorded_by,
        reference_type='CustomerCreditSale',
        reference_id=invoice_number,
    )


@transaction.atomic
def record_customer_payment(
    customer: Customer,
    amount: Decimal,
    payment_method: str,
    recorded_by,
    reference_number: str = '',
    notes: str = '',
    payment_date = None
) -> CustomerPayment:
    """
    Record customer payment collection against outstanding credit debt:
    1. Creates CustomerPayment receipt.
    2. Deducts amount from customer.current_balance.
    3. If cash, records Cash Book inflow.
    4. Posts double-entry:
       Debit: Cash in Drawer (1010) or Bank (1020)
       Credit: Accounts Receivable - Customer (1050)
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError(_("Payment amount must be greater than zero."))

    receipt_num = generate_customer_receipt_number()
    p_date = payment_date or timezone.now().date()

    payment = CustomerPayment.objects.create(
        receipt_number=receipt_num,
        customer=customer,
        payment_date=p_date,
        amount=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        recorded_by=recorded_by,
        notes=notes,
    )
    payment.clean()
    payment.save()

    # Deduct customer credit balance
    locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
    locked_customer.current_balance = max(locked_customer.current_balance - amount, Decimal('0.00'))
    locked_customer.save(update_fields=['current_balance', 'updated_at'])

    # Record Cash Book if cash
    if payment_method == 'CASH':
        record_cash_transaction(
            transaction_type='INFLOW',
            source_category='CUSTOMER_COLLECTION',
            amount=amount,
            performed_by=recorded_by,
            description=f"Credit recovery from {customer.name} (Receipt #{receipt_num})",
            reference_type='CustomerPayment',
            reference_id=receipt_num,
            date=p_date
        )

    # Double-entry Journal Entry
    get_or_create_default_accounts()
    ar_account = Account.objects.get(account_number='1050')
    debit_account = Account.objects.get(account_number='1010' if payment_method == 'CASH' else '1020')

    create_journal_entry(
        date=p_date,
        description=f"Customer credit receipt from {customer.name} via {payment_method} (Receipt #{receipt_num})",
        lines_data=[
            {'account': debit_account, 'debit': amount, 'credit': Decimal('0.00'), 'description': f"Collection via {payment_method}"},
            {'account': ar_account, 'debit': Decimal('0.00'), 'credit': amount, 'description': f"Credit recovery {customer.name}"},
        ],
        created_by=recorded_by,
        reference_type='CustomerPayment',
        reference_id=receipt_num,
    )

    return payment
