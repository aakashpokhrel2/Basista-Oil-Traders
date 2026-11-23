from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.expenses.models import ExpenseCategory, Expense
from apps.accounting.models import Account
from apps.accounting.services import (
    create_journal_entry, record_cash_transaction, get_or_create_default_accounts
)
from common.date_utils import get_current_bs_date


DEFAULT_EXPENSE_CATEGORIES = [
    ('Electricity & Generator Fuel', 'विद्युत तथा जेनेरेटर इन्धन', 'EXP_ELEC', 'NEA electricity bill & generator fuel costs'),
    ('Staff Salaries & Wages', 'कर्मचारी तलब तथा ज्याला', 'EXP_SAL', 'Monthly salaries, operator allowances & overtime'),
    ('Station Rent & Land Lease', 'पम्प जग्गा तथा भवन भाडा', 'EXP_RENT', 'Monthly land & station premises rental'),
    ('Repairs & Nozzle Maintenance', 'पम्प तथा नोजल मर्मत सम्भार', 'EXP_REPAIR', 'Dispenser calibration, hose and nozzle repairs'),
    ('Transportation & Tanker Freight', 'ढुवानी तथा यातायात खर्च', 'EXP_TRANS', 'Tanker transport, local vehicle & courier'),
    ('Office, Printing & Stationery', 'कार्यालय तथा स्टेशनरी खर्च', 'EXP_OFFICE', 'Receipt rolls, invoices, tea and snacks'),
    ('Government Taxes & NOC Inspection', 'सरकारी कर तथा नवीकरण दस्तुर', 'EXP_TAX', 'NOC inspection, municipal tax & environment fee'),
    ('Miscellaneous Operating Expenses', 'विविध सञ्चालन खर्च', 'EXP_MISC', 'Other daily petrol station operating costs'),
]


def seed_default_expense_categories():
    """Seed baseline operational expense categories."""
    for name_en, name_ne, code, desc in DEFAULT_EXPENSE_CATEGORIES:
        ExpenseCategory.objects.get_or_create(
            code=code,
            defaults={
                'name_en': name_en,
                'name_ne': name_ne,
                'description': desc,
                'is_active': True,
            }
        )


def generate_expense_voucher_number() -> str:
    """Generate sequential Expense Voucher Number: EXP-YYYY-XXXXX"""
    bs_today = get_current_bs_date()
    year = bs_today.year if bs_today else timezone.now().year
    prefix = f"EXP-{year}-"
    last_exp = Expense.objects.filter(voucher_number__startswith=prefix).order_by('-voucher_number').first()
    if last_exp:
        try:
            seq = int(last_exp.voucher_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


CATEGORY_ACCOUNT_MAP = {
    'EXP_ELEC': '6010',
    'EXP_SAL': '6020',
    'EXP_RENT': '6030',
    'EXP_REPAIR': '6040',
    'EXP_TRANS': '6050',
    'EXP_OFFICE': '6060',
    'EXP_TAX': '6070',
    'EXP_MISC': '6090',
}


@transaction.atomic
def record_and_approve_expense(
    category: ExpenseCategory,
    amount: Decimal,
    description: str,
    payment_method: str,
    recorded_by,
    payee_name: str = '',
    reference_number: str = '',
    supporting_document = None,
    approved_by = None,
    expense_date = None
) -> Expense:
    """
    Create and approve an operating expense voucher:
    1. Creates Expense record.
    2. If cash, records Cash Book outflow.
    3. Posts double-entry:
       Debit: Operating Expense Account (60xx)
       Credit: Cash in Drawer (1010) or Bank (1020)
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError(_("Expense amount must be greater than zero."))

    v_num = generate_expense_voucher_number()
    exp_date = expense_date or timezone.now().date()

    expense = Expense.objects.create(
        voucher_number=v_num,
        date=exp_date,
        category=category,
        amount=amount,
        description=description,
        payee_name=payee_name,
        payment_method=payment_method,
        reference_number=reference_number,
        supporting_document=supporting_document,
        approval_status='APPROVED',
        recorded_by=recorded_by,
        approved_by=approved_by or recorded_by,
        approved_at=timezone.now(),
    )
    expense.clean()
    expense.save()

    # Cash book entry
    if payment_method == 'CASH':
        record_cash_transaction(
            transaction_type='OUTFLOW',
            source_category='EXPENSE',
            amount=amount,
            performed_by=recorded_by,
            description=f"Expense ({category.name_en}): {description[:50]} (Voucher #{v_num})",
            reference_type='Expense',
            reference_id=v_num,
            date=exp_date
        )

    # Double-entry Journal Entry
    get_or_create_default_accounts()
    acct_code = CATEGORY_ACCOUNT_MAP.get(category.code, '6090')
    exp_account = Account.objects.get(account_number=acct_code)
    credit_account = Account.objects.get(account_number='1010' if payment_method == 'CASH' else '1020')

    create_journal_entry(
        date=exp_date,
        description=f"Expense: {category.name_en} - {description} (Voucher #{v_num})",
        lines_data=[
            {'account': exp_account, 'debit': amount, 'credit': Decimal('0.00'), 'description': f"{category.name_en}: {payee_name}"},
            {'account': credit_account, 'debit': Decimal('0.00'), 'credit': amount, 'description': f"Paid via {payment_method}"},
        ],
        created_by=recorded_by,
        reference_type='Expense',
        reference_id=v_num,
    )

    return expense
