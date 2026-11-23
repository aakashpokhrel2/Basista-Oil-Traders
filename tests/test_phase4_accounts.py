"""
Comprehensive automated tests for Phase 4:
Suppliers, Fuel Purchases, Supplier Payments, Customer Credit,
Operating Expenses, Cash Book, and Double-Entry Accounting Foundation.
"""

from decimal import Decimal
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.station.models import FuelType, StorageTank
from apps.accounting.models import Account, JournalEntry, JournalLine, CashTransaction
from apps.accounting.services import (
    get_or_create_default_accounts,
    create_journal_entry,
    reverse_journal_entry,
    record_cash_transaction,
)
from apps.purchases.models import Supplier, FuelPurchase, SupplierPayment
from apps.purchases.services import approve_fuel_purchase, record_supplier_payment
from apps.customers.models import Customer, CustomerPayment
from apps.customers.services import record_customer_credit_charge, record_customer_payment
from apps.expenses.models import ExpenseCategory, Expense
from apps.expenses.services import record_and_approve_expense, seed_default_expense_categories

User = get_user_model()


class Phase4AccountsTestCase(TestCase):
    """Test suite for Phase 4 Purchases, Customers, Expenses & Accounting."""

    def setUp(self):
        # 1. Users
        self.owner = User.objects.create_user(
            username='owner_p4',
            email='owner4@petrolstation.np',
            password='Password123!',
            role='OWNER'
        )
        self.accountant = User.objects.create_user(
            username='accountant_p4',
            email='accountant4@petrolstation.np',
            password='Password123!',
            role='ACCOUNTANT'
        )

        # 2. Accounting Setup
        get_or_create_default_accounts()
        seed_default_expense_categories()

        # 3. Fuel & Tank Setup
        self.ms, _ = FuelType.objects.get_or_create(
            code='MS',
            defaults={'name_en': 'Petrol (MS)', 'name_ne': 'पेट्रोल', 'unit': 'Litres', 'is_active': True}
        )
        self.tank_ms = StorageTank.objects.create(
            tank_number='T-TEST-MS',
            tank_name='Underground MS Tank Test',
            fuel_type=self.ms,
            capacity_liters=Decimal('20000.00'),
            current_stock=Decimal('5000.00'),
            is_active=True
        )

        # 4. Supplier
        self.supplier = Supplier.objects.create(
            name="Nepal Oil Corporation Test Depot",
            phone="051-521100",
            pan_vat_number="100099887",
            opening_payable_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            status='ACTIVE'
        )

        # 5. Customer
        self.customer = Customer.objects.create(
            name="Prithvi Highway Transport",
            phone="9851122334",
            pan_vat_number="302911223",
            credit_limit=Decimal('200000.00'),
            current_balance=Decimal('50000.00'),
            status='ACTIVE'
        )

    # --------------------------------------------------------------------------
    # 1. Double-Entry Accounting Integrity Tests
    # --------------------------------------------------------------------------

    def test_balanced_journal_entry_success(self):
        """Total Debits must equal Total Credits for every journal entry."""
        cash_acct = Account.objects.get(account_number='1010')
        capital_acct = Account.objects.get(account_number='3010')

        entry = create_journal_entry(
            date=timezone.now().date(),
            description="Initial owner capital deposit",
            lines_data=[
                {'account': cash_acct, 'debit': Decimal('50000.00'), 'credit': Decimal('0.00')},
                {'account': capital_acct, 'debit': Decimal('0.00'), 'credit': Decimal('50000.00')},
            ],
            created_by=self.accountant
        )

        self.assertIsNotNone(entry.pk)
        self.assertEqual(entry.total_amount, Decimal('50000.00'))
        self.assertTrue(entry.is_posted)

        # Verify net balances
        self.assertEqual(cash_acct.current_balance, Decimal('50000.00'))
        self.assertEqual(capital_acct.current_balance, Decimal('50000.00'))

    def test_unbalanced_journal_entry_rejected(self):
        """Attempting to post an unbalanced voucher (Debits != Credits) raises ValidationError."""
        cash_acct = Account.objects.get(account_number='1010')
        capital_acct = Account.objects.get(account_number='3010')

        with self.assertRaises(ValidationError) as ctx:
            create_journal_entry(
                date=timezone.now().date(),
                description="Unbalanced entry",
                lines_data=[
                    {'account': cash_acct, 'debit': Decimal('50000.00'), 'credit': Decimal('0.00')},
                    {'account': capital_acct, 'debit': Decimal('0.00'), 'credit': Decimal('45000.00')},  # 5,000 diff!
                ],
                created_by=self.accountant
            )
        self.assertIn("Double-entry imbalance", str(ctx.exception))

    def test_journal_entry_reversal(self):
        """Reversing a journal voucher creates compensating inverse entries without deleting history."""
        cash_acct = Account.objects.get(account_number='1010')
        capital_acct = Account.objects.get(account_number='3010')

        orig_entry = create_journal_entry(
            date=timezone.now().date(),
            description="Capital deposit to be reversed",
            lines_data=[
                {'account': cash_acct, 'debit': Decimal('20000.00'), 'credit': Decimal('0.00')},
                {'account': capital_acct, 'debit': Decimal('0.00'), 'credit': Decimal('20000.00')},
            ],
            created_by=self.accountant
        )
        self.assertEqual(cash_acct.current_balance, Decimal('20000.00'))

        # Reverse the entry
        reversal_entry = reverse_journal_entry(
            entry=orig_entry,
            reversed_by=self.owner,
            reversal_reason="Mistaken amount entered by clerk"
        )

        orig_entry.refresh_from_db()
        self.assertTrue(orig_entry.is_reversed)
        self.assertEqual(orig_entry.reversed_by_entry, reversal_entry)

        # Net balance returned to zero
        self.assertEqual(cash_acct.current_balance, Decimal('0.00'))
        self.assertEqual(capital_acct.current_balance, Decimal('0.00'))

    # --------------------------------------------------------------------------
    # 2. Fuel Purchase & Tank Inward Tests
    # --------------------------------------------------------------------------

    def test_purchase_approval_updates_stock_and_payables(self):
        """
        Approving a fuel purchase:
        - Updates status to APPROVED
        - Adds fuel quantity into storage tank
        - Increases supplier payable balance
        - Posts inventory and payable journal entry
        """
        initial_stock = self.tank_ms.current_stock
        initial_payable = self.supplier.current_balance

        purchase = FuelPurchase.objects.create(
            supplier=self.supplier,
            invoice_number="NOC-TEST-001",
            purchase_date=timezone.now().date(),
            fuel_type=self.ms,
            receiving_tank=self.tank_ms,
            delivered_quantity=Decimal('8000.00'),
            purchase_price=Decimal('150.00'),
            total_amount=Decimal('1200000.00'),
            tanker_number="Na 7 Kha 1122",
            created_by=self.accountant
        )

        approve_fuel_purchase(purchase=purchase, approved_by=self.owner)

        purchase.refresh_from_db()
        self.assertEqual(purchase.approval_status, 'APPROVED')
        self.assertEqual(purchase.approved_by, self.owner)

        # Storage tank stock updated (+8,000 L)
        self.tank_ms.refresh_from_db()
        self.assertEqual(self.tank_ms.current_stock, initial_stock + Decimal('8000.00'))

        # Supplier payable increased (+1,200,000 NPR)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.current_balance, initial_payable + Decimal('1200000.00'))

        # Inventory asset account updated
        inv_acct = Account.objects.get(account_number='1060')
        self.assertEqual(inv_acct.current_balance, Decimal('1200000.00'))

    def test_purchase_capacity_overflow_prevented(self):
        """Delivering more fuel than tank available capacity raises ValidationError."""
        self.tank_ms.current_stock = Decimal('18000.00')  # Capacity is 20,000 L (only 2,000 L room)
        self.tank_ms.save()

        purchase = FuelPurchase.objects.create(
            supplier=self.supplier,
            invoice_number="NOC-TEST-OVERFLOW",
            purchase_date=timezone.now().date(),
            fuel_type=self.ms,
            receiving_tank=self.tank_ms,
            delivered_quantity=Decimal('5000.00'),  # 5,000 L will overflow 20,000 L
            purchase_price=Decimal('150.00'),
            total_amount=Decimal('750000.00'),
            created_by=self.accountant
        )

        with self.assertRaises(ValidationError) as ctx:
            approve_fuel_purchase(purchase=purchase, approved_by=self.owner)
        self.assertIn("Capacity overflow", str(ctx.exception))

    def test_duplicate_supplier_invoice_prevented(self):
        """Duplicate invoice number from same supplier violates unique constraint."""
        FuelPurchase.objects.create(
            supplier=self.supplier,
            invoice_number="NOC-DUP-01",
            fuel_type=self.ms,
            receiving_tank=self.tank_ms,
            delivered_quantity=Decimal('1000.00'),
            purchase_price=Decimal('150.00'),
            total_amount=Decimal('150000.00'),
            created_by=self.accountant
        )
        with self.assertRaises(Exception):
            FuelPurchase.objects.create(
                supplier=self.supplier,
                invoice_number="NOC-DUP-01",  # Duplicate!
                fuel_type=self.ms,
                receiving_tank=self.tank_ms,
                delivered_quantity=Decimal('2000.00'),
                purchase_price=Decimal('150.00'),
                total_amount=Decimal('300000.00'),
                created_by=self.accountant
            )

    # --------------------------------------------------------------------------
    # 3. Supplier Payments & Cash Book
    # --------------------------------------------------------------------------

    def test_supplier_cash_payment(self):
        """Cash payment to supplier reduces debt and posts Cash Book outflow."""
        # Initial cash in drawer
        record_cash_transaction(
            transaction_type='INFLOW',
            source_category='CAPITAL_INJECTION',
            amount=Decimal('100000.00'),
            performed_by=self.owner,
            description="Drawer initial float"
        )
        initial_payable = self.supplier.current_balance  # 100,000

        payment = record_supplier_payment(
            supplier=self.supplier,
            amount=Decimal('30000.00'),
            payment_method='CASH',
            recorded_by=self.accountant,
            notes="Cash payment to depot cashier"
        )

        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.current_balance, initial_payable - Decimal('30000.00'))

        # Cash Book balance reduced: 100,000 - 30,000 = 70,000
        latest_cash = CashTransaction.objects.order_by('-id').first()
        self.assertEqual(latest_cash.balance_after, Decimal('70000.00'))
        self.assertEqual(latest_cash.transaction_type, 'OUTFLOW')

    # --------------------------------------------------------------------------
    # 4. Customer Credit Management Tests
    # --------------------------------------------------------------------------

    def test_customer_credit_sale_and_limit_check(self):
        """Credit sale increases customer debt up to approved credit limit."""
        # Current balance is 50,000, limit is 200,000
        record_customer_credit_charge(
            customer=self.customer,
            amount=Decimal('80000.00'),
            invoice_number='INV-2083-00099',
            fuel_code='MS',
            recorded_by=self.accountant
        )

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.current_balance, Decimal('130000.00'))
        self.assertEqual(self.customer.available_credit, Decimal('70000.00'))

    def test_customer_credit_limit_exceeded_rejected(self):
        """Attempting to charge credit beyond approved limit raises ValidationError."""
        # Balance 50,000 + 160,000 = 210,000 > Limit 200,000
        with self.assertRaises(ValidationError) as ctx:
            record_customer_credit_charge(
                customer=self.customer,
                amount=Decimal('160000.00'),
                invoice_number='INV-2083-OVER',
                fuel_code='MS',
                recorded_by=self.accountant
            )
        self.assertIn("Credit limit exceeded", str(ctx.exception))

    def test_customer_credit_collection_and_repayment(self):
        """Collecting payment from customer reduces credit balance and posts receipt."""
        initial_balance = self.customer.current_balance  # 50,000

        payment = record_customer_payment(
            customer=self.customer,
            amount=Decimal('35000.00'),
            payment_method='CASH',
            recorded_by=self.accountant,
            notes="Credit collection cash payment"
        )

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.current_balance, initial_balance - Decimal('35000.00'))

        # Cash Book balance increased
        latest_cash = CashTransaction.objects.order_by('-id').first()
        self.assertEqual(latest_cash.transaction_type, 'INFLOW')
        self.assertEqual(latest_cash.source_category, 'CUSTOMER_COLLECTION')

    # --------------------------------------------------------------------------
    # 5. Operating Expenses & Vouchers
    # --------------------------------------------------------------------------

    def test_operating_expense_voucher_and_accounting(self):
        """Recording expense creates voucher, posts Cash Book outflow, and debits expense."""
        cat_elec = ExpenseCategory.objects.get(code='EXP_ELEC')

        expense = record_and_approve_expense(
            category=cat_elec,
            amount=Decimal('12000.00'),
            description="Monthly electricity bill for pump and high-mast lights",
            payment_method='CASH',
            payee_name="NEA Simara",
            recorded_by=self.accountant
        )

        self.assertEqual(expense.approval_status, 'APPROVED')
        self.assertTrue(expense.voucher_number.startswith('EXP-'))

        # Check expense account balance
        elec_acct = Account.objects.get(account_number='6010')
        self.assertEqual(elec_acct.current_balance, Decimal('12000.00'))
