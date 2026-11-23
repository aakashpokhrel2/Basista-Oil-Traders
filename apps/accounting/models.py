import datetime
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from common.date_utils import ad_to_bs


class FinancialPeriod(models.Model):
    """
    Nepali fiscal financial period (e.g., FY 2081/82, 2082/83).
    """
    name = models.CharField(max_length=100, verbose_name=_('Period Name'))
    fiscal_year_bs = models.CharField(max_length=20, unique=True, verbose_name=_('Fiscal Year (BS)'))
    start_date_ad = models.DateField(verbose_name=_('Start Date (AD)'))
    end_date_ad = models.DateField(verbose_name=_('End Date (AD)'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    is_closed = models.BooleanField(default=False, verbose_name=_('Is Closed'))

    class Meta:
        verbose_name = _('Financial Period')
        verbose_name_plural = _('Financial Periods')
        ordering = ['-start_date_ad']

    def __str__(self):
        return f"{self.name} ({self.fiscal_year_bs} BS)"


class Account(models.Model):
    """
    Chart of Accounts (COA) for double-entry financial accounting.
    Enforces standard 5-part accounting classification:
    Assets (1xxx), Liabilities (2xxx), Equity (3xxx), Revenue (4xxx), Expenses (5xxx/6xxx).
    """
    ACCOUNT_TYPE_CHOICES = [
        ('ASSET', _('Asset / सम्पत्ति')),
        ('LIABILITY', _('Liability / दायित्व')),
        ('EQUITY', _('Equity / पुँजी')),
        ('REVENUE', _('Revenue / आम्दानी')),
        ('EXPENSE', _('Expense / खर्च')),
    ]

    account_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name=_('Account Code / Number'),
        help_text=_('e.g., 1010 for Cash Drawer, 1060 for Fuel Inventory, 2010 for Payables')
    )
    name_en = models.CharField(max_length=150, verbose_name=_('Account Name (EN)'))
    name_ne = models.CharField(max_length=150, verbose_name=_('Account Name (NE)'))
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        verbose_name=_('Account Classification')
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('Parent Account')
    )
    is_system_default = models.BooleanField(
        default=False,
        verbose_name=_('System Critical Account'),
        help_text=_('System default accounts cannot be deleted or re-classified.')
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Active Status'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Chart of Account')
        verbose_name_plural = _('Chart of Accounts')
        ordering = ['account_number']

    def __str__(self):
        return f"{self.account_number} - {self.name_en} ({self.name_ne})"

    @property
    def current_balance(self) -> Decimal:
        """
        Compute net debit or net credit balance depending on normal account balance.
        Assets & Expenses: Debit normal (Debits - Credits)
        Liabilities, Equity, Revenue: Credit normal (Credits - Debits)
        """
        lines = self.journal_lines.filter(journal_entry__is_posted=True)
        tot_debit = lines.aggregate(models.Sum('debit'))['debit__sum'] or Decimal('0.00')
        tot_credit = lines.aggregate(models.Sum('credit'))['credit__sum'] or Decimal('0.00')

        if self.account_type in ['ASSET', 'EXPENSE']:
            return tot_debit - tot_credit
        else:
            return tot_credit - tot_debit


class JournalEntry(models.Model):
    """
    General Journal Header.
    Enforces accounting axiom: Total Debits must equal Total Credits.
    Posted entries are immutable; corrections require compensatory reversal entries.
    """
    entry_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name=_('Journal Voucher #')
    )
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Entry Date (AD)')
    )
    date_bs = models.CharField(
        max_length=30,
        verbose_name=_('Entry Date (BS)')
    )
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='journal_entries',
        verbose_name=_('Financial Period')
    )
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Source Document Type'),
        help_text=_('e.g. FuelPurchase, FuelSale, SupplierPayment, CustomerPayment, Expense')
    )
    reference_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Source Document Reference #')
    )
    description = models.TextField(verbose_name=_('Narration / Description'))
    is_posted = models.BooleanField(
        default=True,
        verbose_name=_('Is Posted to Ledger')
    )
    is_reversed = models.BooleanField(
        default=False,
        verbose_name=_('Is Reversed')
    )
    reversed_by_entry = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversal_of',
        verbose_name=_('Reversal Voucher')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='journal_entries_created',
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Journal Entry')
        verbose_name_plural = _('Journal Entries')
        ordering = ['-date', '-entry_number']

    def __str__(self):
        return f"{self.entry_number} [{self.date}] - {self.description[:50]}"

    def clean(self):
        """Auto-populate BS date if missing."""
        if not self.date_bs and self.date:
            bs_obj = ad_to_bs(self.date)
            if bs_obj:
                self.date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"

    def validate_double_entry_balance(self):
        """
        Verify Total Debits == Total Credits.
        Raises ValidationError if unbalanced.
        """
        lines = self.lines.all()
        if not lines.exists():
            raise ValidationError(_("Journal entry must have at least two journal lines."))

        total_debits = sum(line.debit for line in lines)
        total_credits = sum(line.credit for line in lines)

        if total_debits != total_credits:
            raise ValidationError(
                _("Double-entry imbalance! Total Debits (%(dr)s) must equal Total Credits (%(cr)s). Difference: %(diff)s.") % {
                    'dr': total_debits,
                    'cr': total_credits,
                    'diff': abs(total_debits - total_credits)
                }
            )

    @property
    def total_amount(self) -> Decimal:
        """Total debit value of this voucher."""
        return sum(line.debit for line in self.lines.all())


class JournalLine(models.Model):
    """
    Double-entry line item belonging to a JournalEntry.
    """
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Journal Entry')
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='journal_lines',
        verbose_name=_('Account')
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Line Narration')
    )
    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Debit (NPR)')
    )
    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Credit (NPR)')
    )

    class Meta:
        verbose_name = _('Journal Line')
        verbose_name_plural = _('Journal Lines')

    def __str__(self):
        return f"{self.account.name_en} | Dr: {self.debit} | Cr: {self.credit}"

    def clean(self):
        if self.debit < 0 or self.credit < 0:
            raise ValidationError(_("Debit and Credit values cannot be negative."))
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(_("A single journal line cannot have both Debit and Credit amounts."))


class CashTransaction(models.Model):
    """
    Continuous Cash Book tracking every physical cash movement in the station drawer and safe.
    Opening Cash, Cash Sales, Cash Purchases, Expenses, Customer Collections, Supplier Payments, Bank Transfers.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('INFLOW', _('Cash Inflow / आम्दानी (+)')),
        ('OUTFLOW', _('Cash Outflow / खर्च (-)')),
    ]

    SOURCE_CATEGORY_CHOICES = [
        ('FUEL_SALE', _('Fuel Sales Cash')),
        ('CUSTOMER_COLLECTION', _('Customer Credit Repayment')),
        ('SUPPLIER_PAYMENT', _('Supplier Cash Payment')),
        ('EXPENSE', _('Operating Expense Payment')),
        ('BANK_DEPOSIT', _('Cash Deposited to Bank')),
        ('BANK_WITHDRAWAL', _('Cash Withdrawn from Bank for Float')),
        ('CAPITAL_INJECTION', _('Owner Capital Cash')),
        ('DISCREPANCY_ADJUSTMENT', _('Cash Difference / Discrepancy Adjustment')),
        ('OTHER', _('Other Cash Transaction')),
    ]

    voucher_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name=_('Cash Voucher #')
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        verbose_name=_('Flow Direction')
    )
    source_category = models.CharField(
        max_length=30,
        choices=SOURCE_CATEGORY_CHOICES,
        db_index=True,
        verbose_name=_('Transaction Source')
    )
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Date (AD)')
    )
    date_bs = models.CharField(
        max_length=30,
        verbose_name=_('Date (BS)')
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Amount (NPR)')
    )
    balance_after = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_('Drawer Cash Balance After (NPR)')
    )
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Reference Type')
    )
    reference_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Reference ID')
    )
    description = models.CharField(
        max_length=255,
        verbose_name=_('Description / Narration')
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name=_('Handled By')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Cash Transaction')
        verbose_name_plural = _('Cash Book Transactions')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.voucher_number} | {self.transaction_type} {self.amount} NPR | Bal: {self.balance_after}"
