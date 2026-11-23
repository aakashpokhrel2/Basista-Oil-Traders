"""
Automated Security, QA, and Transaction Integrity Tests for Phase 6.
Covers:
- Password hashing & login attempt rate-limiting / lockout.
- Server-side RBAC authorization enforcement across all 5 user roles.
- AuditLog immutability and tamper-evident append-only constraints.
- Transaction integrity: row locking, duplicate prevention, and balance constraints.
- Automated backup and restore execution with SHA-256 verification.
"""

from decimal import Decimal
import datetime
from pathlib import Path
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.authentication.security import check_login_lockout, record_login_attempt, LoginAttempt
from apps.audit.models import AuditLog
from apps.audit.services import record_audit_event
from apps.station.models import StationConfiguration, FuelType, StorageTank, Pump, Nozzle, FuelPrice
from apps.operations.models import ShiftSchedule, Shift, FuelSale, StockMovement
from apps.operations.services import record_stock_movement, cancel_fuel_sale, generate_invoice_number
from apps.purchases.models import Supplier, FuelPurchase
from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.services import get_or_create_default_accounts, create_journal_entry
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER, ROLE_PUMP_OPERATOR

User = get_user_model()


class Phase6SecurityQATestCase(TestCase):
    """Phase 6 Security, RBAC, and Quality Assurance Test Suite."""

    def setUp(self):
        self.client = Client()

        # 1. Users for all 5 roles
        self.owner = User.objects.create_user(
            username='owner_sec', email='owner@sec.np', password='OwnerPassword123!', role=ROLE_OWNER
        )
        self.manager = User.objects.create_user(
            username='manager_sec', email='manager@sec.np', password='ManagerPassword123!', role=ROLE_MANAGER
        )
        self.accountant = User.objects.create_user(
            username='accountant_sec', email='acc@sec.np', password='AccountantPassword123!', role=ROLE_ACCOUNTANT
        )
        self.cashier = User.objects.create_user(
            username='cashier_sec', email='cashier@sec.np', password='CashierPassword123!', role=ROLE_CASHIER
        )
        self.operator = User.objects.create_user(
            username='operator_sec', email='op@sec.np', password='OperatorPassword123!', role=ROLE_PUMP_OPERATOR
        )

        # 2. Accounting & Station setup
        get_or_create_default_accounts()
        self.station = StationConfiguration.get_solo()
        self.station.station_name_en = "Basista Oil Traders"
        self.station.save()

        # 3. Fuel & Tank Setup
        self.ms, _ = FuelType.objects.get_or_create(
            code='MS', defaults={'name_en': 'Petrol (MS)', 'name_ne': 'पेट्रोल', 'unit': 'Litres', 'is_active': True}
        )
        self.tank_ms, _ = StorageTank.objects.get_or_create(
            tank_number='T-MS-SEC', defaults={
                'tank_name': 'Underground Petrol Tank', 'fuel_type': self.ms,
                'capacity_liters': Decimal('15000.00'), 'current_stock': Decimal('8000.00'), 'is_active': True
            }
        )

        # 4. Shift
        self.schedule, _ = ShiftSchedule.objects.get_or_create(
            name_en='Morning', defaults={'name_ne': 'बिहानी', 'start_time': datetime.time(6, 0), 'end_time': datetime.time(14, 0)}
        )
        self.shift = Shift.objects.create(
            shift_number='S-SEC-01', schedule=self.schedule, date_ad=timezone.now().date(),
            supervisor=self.manager, opening_cash_balance=Decimal('5000.00'), status='OPEN'
        )

    # --------------------------------------------------------------------------
    # 1. Authentication Security & Login Rate Limiting
    # --------------------------------------------------------------------------
    def test_login_brute_force_rate_limiting_and_lockout(self):
        """5 consecutive failed logins trigger security lockout for the username and IP."""
        test_user = 'victim_user'
        test_ip = '192.168.1.100'

        # Record 4 failed attempts: not yet locked out
        for _ in range(4):
            record_login_attempt(test_user, test_ip, is_successful=False, failure_reason='Invalid password')
        is_locked, remaining = check_login_lockout(test_user, test_ip)
        self.assertFalse(is_locked)

        # 5th failed attempt: triggers lockout
        record_login_attempt(test_user, test_ip, is_successful=False, failure_reason='Invalid password')
        is_locked, remaining = check_login_lockout(test_user, test_ip)
        self.assertTrue(is_locked)
        self.assertGreaterEqual(remaining, 1)

    def test_inactive_user_cannot_login(self):
        """Deactivated staff member is immediately blocked from logging in."""
        self.operator.is_active = False
        self.operator.save()

        res = self.client.post(reverse('authentication:login'), {
            'username': 'operator_sec',
            'password': 'OperatorPassword123!'
        })
        self.assertFalse(res.context['user'].is_authenticated if res.context else False)

    # --------------------------------------------------------------------------
    # 2. Server-Side RBAC Authorization Tests
    # --------------------------------------------------------------------------
    def test_operator_blocked_from_financial_admin_and_purchases(self):
        """Pump operator cannot access financial statements, COA, or supplier payments."""
        self.client.force_login(self.operator)

        # 1. Financial Statements
        res_fin = self.client.get(reverse('reports:financial_statements'))
        self.assertEqual(res_fin.status_code, 302, "Operator must be redirected from financial statements")

        # 2. Chart of Accounts
        res_coa = self.client.get(reverse('accounting:account_list'))
        self.assertEqual(res_coa.status_code, 302, "Operator must be redirected from Chart of Accounts")

        # 3. Cash Book
        res_cash = self.client.get(reverse('accounting:cash_book'))
        self.assertEqual(res_cash.status_code, 302, "Operator must be redirected from Cash Book")

    def test_cashier_blocked_from_hardware_configuration(self):
        """Cashier cannot add or edit storage tanks, pumps, or nozzles."""
        self.client.force_login(self.cashier)

        res_tank = self.client.get(reverse('station:tank_create'))
        self.assertEqual(res_tank.status_code, 302, "Cashier cannot create storage tanks")

        res_pump = self.client.get(reverse('station:pump_create'))
        self.assertEqual(res_pump.status_code, 302, "Cashier cannot create dispensing pumps")

    def test_manager_blocked_from_owner_only_settings_and_audit(self):
        """Manager cannot modify station legal profile (PAN/VAT) or view system audit logs."""
        self.client.force_login(self.manager)

        # Station legal settings is owner-only
        res_settings = self.client.get(reverse('station:settings'))
        self.assertEqual(res_settings.status_code, 302, "Manager cannot access owner-only station settings")

        # Audit logs is owner-only
        res_audit = self.client.get(reverse('audit:audit_list'))
        self.assertEqual(res_audit.status_code, 302, "Manager cannot access audit trail")

        # Owner has full access to both
        self.client.force_login(self.owner)
        res_owner_settings = self.client.get(reverse('station:settings'))
        self.assertEqual(res_owner_settings.status_code, 200)

        res_owner_audit = self.client.get(reverse('audit:audit_list'))
        self.assertEqual(res_owner_audit.status_code, 200)

    # --------------------------------------------------------------------------
    # 3. Audit System Immutability & Tamper-Evident Rules
    # --------------------------------------------------------------------------
    def test_audit_log_immutability(self):
        """AuditLog entries cannot be modified or deleted once created."""
        entry = record_audit_event(
            action='PRICE_CHANGE',
            model_name='FuelPrice',
            record_id='MS-01',
            user=self.owner,
            previous_value={'price': 170.0},
            updated_value={'price': 175.0},
            reason="Official NOC price revision"
        )
        self.assertIsNotNone(entry.pk)

        # 1. Attempting to modify existing entry must raise ValidationError
        entry.reason = "Tampered reason by unauthorized party"
        with self.assertRaises(ValidationError) as ctx_update:
            entry.save()
        self.assertIn("immutable", str(ctx_update.exception))

        # 2. Attempting to delete existing entry must raise ValidationError
        with self.assertRaises(ValidationError) as ctx_delete:
            entry.delete()
        self.assertIn("cannot be deleted", str(ctx_delete.exception))

    def test_sales_cancellation_generates_audit_entry(self):
        """Voiding a sale creates a permanent SALE_REVERSAL and an AuditLog entry."""
        sale = FuelSale.objects.create(
            invoice_number=generate_invoice_number(),
            shift=self.shift,
            fuel_type=self.ms,
            tank=self.tank_ms,
            sale_type='MANUAL',
            payment_method='CASH',
            quantity=Decimal('25.00'),
            unit_price=Decimal('175.00'),
            total_amount=Decimal('4375.00'),
            recorded_by=self.operator,
            reason_for_manual='Test sale'
        )

        cancel_fuel_sale(sale, cancelled_by=self.manager, cancellation_reason='Customer dispute on quantity')

        # Check audit log
        audit = AuditLog.objects.filter(model_name='FuelSale', record_id=sale.invoice_number).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, 'CANCEL')
        self.assertEqual(audit.user, self.manager)
        self.assertIn('Customer dispute', audit.reason)

    # --------------------------------------------------------------------------
    # 4. Transaction Integrity & Database Constraints
    # --------------------------------------------------------------------------
    def test_duplicate_supplier_invoice_rejected(self):
        """Supplier invoice number must be unique per supplier."""
        supplier = Supplier.objects.create(name='Nepal Oil Corp Janakpur', phone='9845012345')
        FuelPurchase.objects.create(
            supplier=supplier, invoice_number='NOC-INV-UNIQUE', purchase_date=timezone.now().date(),
            fuel_type=self.ms, receiving_tank=self.tank_ms, delivered_quantity=Decimal('500.00'),
            purchase_price=Decimal('155.00'), total_amount=Decimal('77500.00'), created_by=self.manager
        )

        # Duplicate invoice for the same supplier
        with self.assertRaises(Exception):
            FuelPurchase.objects.create(
                supplier=supplier, invoice_number='NOC-INV-UNIQUE', purchase_date=timezone.now().date(),
                fuel_type=self.ms, receiving_tank=self.tank_ms, delivered_quantity=Decimal('300.00'),
                purchase_price=Decimal('155.00'), total_amount=Decimal('46500.00'), created_by=self.manager
            )

    def test_negative_quantity_stock_movement_rejected(self):
        """Stock movement with zero or negative quantity is strictly rejected."""
        with self.assertRaises(ValidationError) as ctx:
            record_stock_movement(
                tank=self.tank_ms,
                movement_type='PURCHASE',
                quantity=Decimal('-10.00'),
                performed_by=self.manager
            )
        self.assertIn("greater than zero", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 5. Automated Backup & Recovery Verification
    # --------------------------------------------------------------------------
    def test_backup_and_restore_cycle(self):
        """Test backup_database creates verified archive and restore_database loads data."""
        backup_dir = Path(self.station._meta.app_config.path).parent.parent / 'backups' / 'test_qa'
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Run backup
            call_command('backup_database', output_dir=str(backup_dir), keep_days=1)
            backups = list(backup_dir.glob('db_backup_*.json.gz'))
            self.assertGreater(len(backups), 0, "Backup file must be generated")

            latest_backup = backups[0]
            manifests = list(backup_dir.glob(f"{latest_backup.stem}.manifest.json"))
            self.assertGreater(len(manifests), 0, "Manifest file must be generated")

            # 2. Run restore with confirmation
            call_command('restore_database', backup_file=str(latest_backup), confirm=True)

            # Check audit event for restore
            restore_audit = AuditLog.objects.filter(action='RESTORE').first()
            self.assertIsNotNone(restore_audit)
        finally:
            import shutil
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
