from decimal import Decimal
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounting.models import (
    FinancialPeriod, Account, JournalEntry, JournalLine, CashTransaction
)
from common.date_utils import ad_to_bs, get_current_bs_date


DEFAULT_ACCOUNTS = [
    # 1. Assets (1xxx)
    ('1010', 'Cash in Drawer / Cash Float', 'नगद मौज्दात', 'ASSET', None),
    ('1020', 'Bank Account - Primary', 'बैंक खाता', 'ASSET', None),
    ('1050', 'Accounts Receivable - Credit Customers', 'उधारो बिक्री प्राप्य खाता', 'ASSET', None),
    ('1060', 'Fuel Inventory - Petrol (MS)', 'पेट्रोल मौज्दात स्टक', 'ASSET', None),
    ('1061', 'Fuel Inventory - Diesel (HSD)', 'डिजेल मौज्दात स्टक', 'ASSET', None),

    # 2. Liabilities (2xxx)
    ('2010', 'Accounts Payable - Fuel Suppliers / NOC', 'एनओसी तिर्नुपर्ने दायित्व खाता', 'LIABILITY', None),

    # 3. Equity (3xxx)
    ('3010', 'Owner Capital / Equity', 'सञ्चालकको पुँजी', 'EQUITY', None),
    ('3020', 'Retained Earnings', 'सञ्चित नाफा', 'EQUITY', None),

    # 4. Revenue (4xxx)
    ('4010', 'Fuel Sales Revenue - Petrol (MS)', 'पेट्रोल बिक्री आम्दानी', 'REVENUE', None),
    ('4020', 'Fuel Sales Revenue - Diesel (HSD)', 'डिजेल बिक्री आम्दानी', 'REVENUE', None),

    # 5. Cost of Goods Sold (5xxx)
    ('5010', 'Cost of Fuel Sold - Petrol (MS)', 'बिक्री भएको पेट्रोलको लागत', 'EXPENSE', None),
    ('5020', 'Cost of Fuel Sold - Diesel (HSD)', 'बिक्री भएको डिजेलको लागत', 'EXPENSE', None),

    # 6. Operating Expenses (6xxx)
    ('6010', 'Electricity & Generator Fuel', 'विद्युत तथा जेनेरेटर इन्धन', 'EXPENSE', None),
    ('6020', 'Staff Salaries & Wages', 'कर्मचारी तलब तथा ज्याला', 'EXPENSE', None),
    ('6030', 'Station Rent & Land Lease', 'पम्प जग्गा तथा भवन भाडा', 'EXPENSE', None),
    ('6040', 'Repairs & Dispenser Maintenance', 'पम्प तथा नोजल मर्मत सम्भार', 'EXPENSE', None),
    ('6050', 'Transportation & Freight', 'ढुवानी तथा यातायात खर्च', 'EXPENSE', None),
    ('6060', 'Office, Printing & Stationery', 'कार्यालय तथा स्टेशनरी खर्च', 'EXPENSE', None),
    ('6070', 'Government Taxes, NOC Fees & Licenses', 'सरकारी कर तथा नवीकरण दस्तुर', 'EXPENSE', None),
    ('6090', 'Miscellaneous Operating Expenses', 'विविध सञ्चालन खर्च', 'EXPENSE', None),
]


def get_or_create_default_accounts():
    """Seed or retrieve baseline chart of accounts."""
    created = []
    for num, name_en, name_ne, acct_type, parent in DEFAULT_ACCOUNTS:
        acct, is_new = Account.objects.get_or_create(
            account_number=num,
            defaults={
                'name_en': name_en,
                'name_ne': name_ne,
                'account_type': acct_type,
                'is_system_default': True,
                'is_active': True,
            }
        )
        if is_new:
            created.append(acct)
    return created


def generate_journal_entry_number() -> str:
    """Generate sequential Journal Voucher number: JV-YYYY-XXXXX"""
    bs_today = get_current_bs_date()
    year = bs_today.year if bs_today else timezone.now().year
    prefix = f"JV-{year}-"
    last_jv = JournalEntry.objects.filter(entry_number__startswith=prefix).order_by('-entry_number').first()
    if last_jv:
        try:
            seq = int(last_jv.entry_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


def generate_cash_voucher_number() -> str:
    """Generate sequential Cash Voucher number: CB-YYYY-XXXXX"""
    bs_today = get_current_bs_date()
    year = bs_today.year if bs_today else timezone.now().year
    prefix = f"CB-{year}-"
    last_cb = CashTransaction.objects.filter(voucher_number__startswith=prefix).order_by('-voucher_number').first()
    if last_cb:
        try:
            seq = int(last_cb.voucher_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


@transaction.atomic
def create_journal_entry(
    date,
    description: str,
    lines_data: list[dict],
    created_by,
    reference_type: str = '',
    reference_id: str = '',
    financial_period: FinancialPeriod = None
) -> JournalEntry:
    """
    Create a validated double-entry journal entry.
    lines_data format: [{'account': Account_obj, 'debit': Decimal, 'credit': Decimal, 'description': str}, ...]
    Enforces Total Debits == Total Credits.
    """
    if len(lines_data) < 2:
        raise ValidationError(_("A double-entry voucher must contain at least 2 line items."))

    total_dr = sum(Decimal(str(item.get('debit', 0))) for item in lines_data)
    total_cr = sum(Decimal(str(item.get('credit', 0))) for item in lines_data)

    if total_dr != total_cr:
        raise ValidationError(
            _("Double-entry imbalance! Total Debits (%(dr)s) != Total Credits (%(cr)s).") % {
                'dr': total_dr,
                'cr': total_cr
            }
        )

    entry_num = generate_journal_entry_number()
    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=date or timezone.now().date(),
        financial_period=financial_period,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        is_posted=True,
        created_by=created_by,
    )
    entry.clean()
    entry.save()

    for item in lines_data:
        JournalLine.objects.create(
            journal_entry=entry,
            account=item['account'],
            description=item.get('description', '') or description,
            debit=Decimal(str(item.get('debit', 0))),
            credit=Decimal(str(item.get('credit', 0))),
        )

    return entry


@transaction.atomic
def reverse_journal_entry(
    entry: JournalEntry,
    reversed_by,
    reversal_reason: str
) -> JournalEntry:
    """
    Reverses an existing posted journal entry by generating an exact inverse entry.
    """
    if entry.is_reversed:
        raise ValidationError(_("This journal entry has already been reversed."))

    inverse_lines = []
    for line in entry.lines.all():
        inverse_lines.append({
            'account': line.account,
            'debit': line.credit,  # swap
            'credit': line.debit,  # swap
            'description': f"Reversal of {entry.entry_number}: {line.description}"
        })

    reversal_entry = create_journal_entry(
        date=timezone.now().date(),
        description=f"REVERSAL of {entry.entry_number}: {reversal_reason}",
        lines_data=inverse_lines,
        created_by=reversed_by,
        reference_type='JournalReversal',
        reference_id=entry.entry_number
    )

    entry.is_reversed = True
    entry.reversed_by_entry = reversal_entry
    entry.save(update_fields=['is_reversed', 'reversed_by_entry'])

    return reversal_entry


@transaction.atomic
def record_cash_transaction(
    transaction_type: str,
    source_category: str,
    amount: Decimal,
    performed_by,
    description: str,
    reference_type: str = '',
    reference_id: str = '',
    date=None
) -> CashTransaction:
    """
    Thread-safe Cash Book entry. Updates cash balance atomically with row locking.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError(_("Cash transaction amount must be greater than zero."))

    last_tx = CashTransaction.objects.select_for_update().order_by('-date', '-created_at', '-id').first()
    current_cash = last_tx.balance_after if last_tx else Decimal('0.00')

    if transaction_type == 'INFLOW':
        new_balance = current_cash + amount
    elif transaction_type == 'OUTFLOW':
        new_balance = current_cash - amount
    else:
        raise ValidationError(f"Invalid transaction type: {transaction_type}")

    tx_date = date or timezone.now().date()
    bs_obj = ad_to_bs(tx_date)
    bs_str = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}" if bs_obj else ""

    voucher = generate_cash_voucher_number()
    tx = CashTransaction.objects.create(
        voucher_number=voucher,
        transaction_type=transaction_type,
        source_category=source_category,
        date=tx_date,
        date_bs=bs_str,
        amount=amount,
        balance_after=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        performed_by=performed_by,
    )
    return tx
