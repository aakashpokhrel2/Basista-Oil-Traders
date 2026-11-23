"""
Comprehensive automated tests for Phase 5:
Executive Dashboard, Business Analytics, Multidimensional Operational Reports,
Underground Inventory Reconciliation, Double-Entry Financial Statements (P&L, Balance Sheet, Trial Balance),
WeasyPrint PDF Reports, and openpyxl Excel Exports.
"""

from decimal import Decimal
import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse

from apps.station.models import StationConfiguration, FuelType, StorageTank, Pump, Nozzle, FuelPrice
from apps.operations.models import ShiftSchedule, Shift, MeterReading, FuelSale, StockMovement
from apps.operations.services import record_stock_movement, record_manual_sale, generate_invoice_number
from apps.purchases.models import Supplier, FuelPurchase
from apps.purchases.services import approve_fuel_purchase
from apps.customers.models import Customer
from apps.customers.services import record_customer_credit_charge
from apps.expenses.models import ExpenseCategory, Expense
from apps.expenses.services import record_and_approve_expense, seed_default_expense_categories
from apps.accounting.models import Account, JournalEntry, JournalLine, CashTransaction
from apps.accounting.services import get_or_create_default_accounts, record_cash_transaction

from apps.reports.services import (
    get_dashboard_charts_data,
    get_operational_sales_report,
    get_inventory_reconciliation_report,
    get_income_statement_data,
    get_balance_sheet_data,
    get_trial_balance_data,
    export_report_to_pdf,
    export_report_to_excel,
)

User = get_user_model()


class Phase5ReportsTestCase(TestCase):
    """Test suite for Phase 5 Dashboard, Reporting and Financial Analytics."""

    def setUp(self):
        self.client = Client()

        # 1. Users
        self.owner = User.objects.create_user(
            username='owner_p5',
            email='owner5@petrolstation.np',
            password='Password123!',
            role='OWNER'
        )
        self.manager = User.objects.create_user(
            username='manager_p5',
            email='manager5@petrolstation.np',
            password='Password123!',
            role='MANAGER'
        )
        self.operator = User.objects.create_user(
            username='operator_p5',
            email='operator5@petrolstation.np',
            password='Password123!',
            role='OPERATOR'
        )

        # 2. Station Configuration
        self.station = StationConfiguration.get_solo()
        self.station.station_name_en = "Basista Oil Traders"
        self.station.save()

        # 3. Chart of Accounts & Expense Categories
        get_or_create_default_accounts()
        seed_default_expense_categories()

        # 4. Fuel & Tanks
        self.ms, _ = FuelType.objects.get_or_create(
            code='MS',
            defaults={'name_en': 'Petrol (MS)', 'name_ne': 'पेट्रोल', 'unit': 'Litres', 'is_active': True}
        )
        self.hsd, _ = FuelType.objects.get_or_create(
            code='HSD',
            defaults={'name_en': 'Diesel (HSD)', 'name_ne': 'डिजेल', 'unit': 'Litres', 'is_active': True}
        )

        self.tank_ms = StorageTank.objects.create(
            tank_number='T-MS-P5',
            tank_name='Underground Tank MS',
            fuel_type=self.ms,
            capacity_liters=Decimal('15000.00'),
            current_stock=Decimal('8000.00'),
            opening_stock=Decimal('8000.00'),
            is_active=True
        )
        self.tank_hsd = StorageTank.objects.create(
            tank_number='T-HSD-P5',
            tank_name='Underground Tank HSD',
            fuel_type=self.hsd,
            capacity_liters=Decimal('20000.00'),
            current_stock=Decimal('12000.00'),
            opening_stock=Decimal('12000.00'),
            is_active=True
        )

        # 5. Prices
        FuelPrice.objects.create(
            fuel_type=self.ms,
            purchase_price=Decimal('155.00'),
            selling_price=Decimal('175.00'),
            effective_date=timezone.now(),
            approval_status='APPROVED',
            created_by=self.owner
        )
        FuelPrice.objects.create(
            fuel_type=self.hsd,
            purchase_price=Decimal('140.00'),
            selling_price=Decimal('158.00'),
            effective_date=timezone.now(),
            approval_status='APPROVED',
            created_by=self.owner
        )

        # 6. Pumps and Nozzles
        self.pump1 = Pump.objects.create(
            pump_number=1,
            pump_name='Dispenser Bay 1',
            status='ACTIVE'
        )
        self.nozzle_ms = Nozzle.objects.create(
            pump=self.pump1,
            nozzle_number=1,
            nozzle_code='P1-N1',
            fuel_type=self.ms,
            tank=self.tank_ms,
            current_meter_reading=Decimal('5000.00'),
            status='ACTIVE'
        )
        self.nozzle_hsd = Nozzle.objects.create(
            pump=self.pump1,
            nozzle_number=2,
            nozzle_code='P1-N2',
            fuel_type=self.hsd,
            tank=self.tank_hsd,
            current_meter_reading=Decimal('8000.00'),
            status='ACTIVE'
        )

        # 7. Shift
        self.schedule = ShiftSchedule.objects.create(
            name_en='Morning Shift',
            name_ne='बिहानी शिफ्ट',
            start_time=datetime.time(6, 0),
            end_time=datetime.time(14, 0),
            is_active=True
        )
        self.shift = Shift.objects.create(
            shift_number='S-P5-001',
            schedule=self.schedule,
            date_ad=timezone.now().date(),
            supervisor=self.manager,
            opening_cash_balance=Decimal('10000.00'),
            status='OPEN'
        )
        self.shift.operators.add(self.operator)

        # 8. Initial Drawer Cash
        record_cash_transaction(
            transaction_type='INFLOW',
            source_category='CAPITAL_INJECTION',
            amount=Decimal('10000.00'),
            performed_by=self.manager,
            description="Shift opening float"
        )

    # --------------------------------------------------------------------------
    # 1. Chart.js Data Structure Tests
    # --------------------------------------------------------------------------
    def test_dashboard_charts_data_generator(self):
        """Test get_dashboard_charts_data generates complete widget structures."""
        # Record a fuel sale to ensure metrics aggregate
        FuelSale.objects.create(
            invoice_number=generate_invoice_number(),
            shift=self.shift,
            nozzle=self.nozzle_ms,
            fuel_type=self.ms,
            tank=self.tank_ms,
            sale_type='METER',
            payment_method='CASH',
            unit_price=Decimal('175.00'),
            quantity=Decimal('40.00'),
            total_amount=Decimal('7000.00'),
            recorded_by=self.operator
        )

        charts_data = get_dashboard_charts_data()
        expected_keys = [
            'daily_labels', 'daily_sales_ms', 'daily_sales_hsd', 'daily_revenue',
            'petrol_vs_diesel', 'expense_labels', 'expense_data',
            'tank_labels', 'tank_current', 'tank_capacity',
            'tot_purchases', 'tot_sales'
        ]
        for key in expected_keys:
            self.assertIn(key, charts_data)

        self.assertEqual(len(charts_data['daily_labels']), 7)
        self.assertGreater(charts_data['tot_sales'], 0)
        self.assertEqual(len(charts_data['tank_labels']), 2)

    # --------------------------------------------------------------------------
    # 2. Operational Sales Report Tests
    # --------------------------------------------------------------------------
    def test_operational_sales_report_groupings(self):
        """Test multidimensional sales reporting across daily, pump, nozzle, employee, shift, and payment."""
        # Create Petrol and Diesel sales
        sale1 = FuelSale.objects.create(
            invoice_number=generate_invoice_number(),
            shift=self.shift,
            nozzle=self.nozzle_ms,
            fuel_type=self.ms,
            tank=self.tank_ms,
            sale_type='METER',
            payment_method='CASH',
            unit_price=Decimal('175.00'),
            quantity=Decimal('50.00'),
            total_amount=Decimal('8750.00'),
            recorded_by=self.operator
        )
        sale2 = FuelSale.objects.create(
            invoice_number=generate_invoice_number(),
            shift=self.shift,
            nozzle=self.nozzle_hsd,
            fuel_type=self.hsd,
            tank=self.tank_hsd,
            sale_type='MANUAL',
            payment_method='BANK_TRANSFER',
            unit_price=Decimal('158.00'),
            quantity=Decimal('100.00'),
            total_amount=Decimal('15800.00'),
            recorded_by=self.manager
        )

        # 1. Daily grouping
        records_daily, totals = get_operational_sales_report(group_by='daily')
        self.assertEqual(totals['grand_volume'], Decimal('150.00'))
        self.assertEqual(totals['grand_revenue'], Decimal('24550.00'))
        self.assertEqual(totals['grand_count'], 2)

        # 2. Pump grouping
        records_pump, _ = get_operational_sales_report(group_by='pump')
        self.assertEqual(len(records_pump), 1)
        self.assertEqual(records_pump[0]['total_qty'], Decimal('150.00'))

        # 3. Nozzle grouping
        records_nozzle, _ = get_operational_sales_report(group_by='nozzle')
        self.assertEqual(len(records_nozzle), 2)

        # 4. Payment grouping
        records_pay, _ = get_operational_sales_report(group_by='payment')
        self.assertEqual(len(records_pay), 2)

        # 5. Filter by fuel code (MS only)
        records_ms, totals_ms = get_operational_sales_report(group_by='daily', fuel_code='MS')
        self.assertEqual(totals_ms['grand_volume'], Decimal('50.00'))
        self.assertEqual(totals_ms['grand_revenue'], Decimal('8750.00'))

    # --------------------------------------------------------------------------
    # 3. Inventory Reconciliation Tests
    # --------------------------------------------------------------------------
    def test_inventory_reconciliation_formula(self):
        """
        Verify Expected Closing = Opening + Purchases - Dispensed + Returns +/- Adjustments
        and Variance calculation against physical actual stock.
        """
        # Starting stock: 8000 L
        # 1. Purchase receipt: +2000 L
        record_stock_movement(
            tank=self.tank_ms,
            movement_type='PURCHASE',
            quantity=Decimal('2000.00'),
            reference_id='NOC-REC-01',
            performed_by=self.manager,
            remarks='Delivered tanker'
        )
        # 2. Dispensed via meter: -500 L
        record_stock_movement(
            tank=self.tank_ms,
            movement_type='SALE_METER',
            quantity=Decimal('500.00'),
            reference_id='SALE-01',
            performed_by=self.operator,
            remarks='Meter dispensing'
        )
        # 3. Calibration return: +10 L
        record_stock_movement(
            tank=self.tank_ms,
            movement_type='TEST_RETURN',
            quantity=Decimal('10.00'),
            reference_id='CALIB-01',
            performed_by=self.manager,
            remarks='5L measure returned to tank'
        )

        rows = get_inventory_reconciliation_report(tank_id=self.tank_ms.id)
        self.assertEqual(len(rows), 1)
        r = rows[0]

        self.assertEqual(r['opening_stock'], Decimal('8000.00'))
        self.assertEqual(r['purchases'], Decimal('2000.00'))
        self.assertEqual(r['dispensed'], Decimal('500.00'))
        self.assertEqual(r['test_returns'], Decimal('10.00'))

        expected = Decimal('8000.00') + Decimal('2000.00') - Decimal('500.00') + Decimal('10.00')
        self.tank_ms.refresh_from_db()
        self.assertEqual(r['expected_closing'], expected)
        self.assertEqual(r['actual_closing'], self.tank_ms.current_stock)
        self.assertEqual(r['variance'], Decimal('0.00'))

    # --------------------------------------------------------------------------
    # 4. Double-Entry Financial Statements Tests
    # --------------------------------------------------------------------------
    def test_income_statement_cogs_and_profit(self):
        """Test Income Statement calculates Revenue, COGS, Gross Profit, and Operating Profit."""
        # 1. Revenue
        FuelSale.objects.create(
            invoice_number=generate_invoice_number(),
            shift=self.shift,
            nozzle=self.nozzle_ms,
            fuel_type=self.ms,
            tank=self.tank_ms,
            sale_type='METER',
            payment_method='CASH',
            unit_price=Decimal('175.00'),
            quantity=Decimal('100.00'),
            total_amount=Decimal('17500.00'),
            recorded_by=self.operator
        )
        # 2. Purchase (COGS)
        supplier = Supplier.objects.create(
            name='Nepal Oil Corporation Amalekhgunj',
            contact_person='Depot Manager',
            phone='9855012345',
            status='ACTIVE'
        )
        purchase = FuelPurchase.objects.create(
            supplier=supplier,
            invoice_number='NOC-INV-P5',
            purchase_date=timezone.now().date(),
            fuel_type=self.ms,
            receiving_tank=self.tank_ms,
            delivered_quantity=Decimal('100.00'),
            purchase_price=Decimal('155.00'),
            total_amount=Decimal('15500.00'),
            created_by=self.manager
        )
        approve_fuel_purchase(purchase=purchase, approved_by=self.owner)

        # 3. Expense
        cat = ExpenseCategory.objects.get(code='EXP_ELEC')
        record_and_approve_expense(
            category=cat,
            amount=Decimal('800.00'),
            description='NEA Generator grid electricity bill',
            payment_method='CASH',
            recorded_by=self.manager,
            approved_by=self.owner
        )

        pnl = get_income_statement_data()
        self.assertEqual(pnl['total_revenue'], Decimal('17500.00'))
        self.assertEqual(pnl['total_cogs'], Decimal('15500.00'))
        self.assertEqual(pnl['gross_profit'], Decimal('2000.00'))
        self.assertEqual(pnl['total_operating_expenses'], Decimal('800.00'))
        self.assertEqual(pnl['net_profit'], Decimal('1200.00'))

    def test_balance_sheet_and_trial_balance(self):
        """Test Balance Sheet Assets = Liabilities + Equity and Trial Balance Dr == Cr."""
        # Assets: Cash in Drawer, Fuel Inventory, Customer Credit
        customer = Customer.objects.create(
            name='Shree Lumbini Transporters',
            phone='9845011111',
            credit_limit=Decimal('50000.00'),
            current_balance=Decimal('15000.00'),
            status='ACTIVE'
        )

        bs = get_balance_sheet_data()
        self.assertGreater(bs['total_assets'], Decimal('0.00'))
        # Identity: Assets = Liabilities + Equity
        self.assertEqual(bs['total_assets'], bs['total_liabilities'] + bs['equity_balance'])

        # Trial Balance
        tb_rows, tot_dr, tot_cr = get_trial_balance_data()
        self.assertEqual(tot_dr, tot_cr, "Trial balance debits must strictly equal credits")

    # --------------------------------------------------------------------------
    # 5. Export Utilities Tests (WeasyPrint PDF & openpyxl Excel)
    # --------------------------------------------------------------------------
    def test_export_report_to_pdf(self):
        """Test WeasyPrint renders valid PDF bytes with Nepali fonts and header."""
        context = {
            'title': 'Test Profit & Loss',
            'pnl': get_income_statement_data(),
            'start_date': None,
            'end_date': None
        }
        response = export_report_to_pdf(
            template_name='reports/pdf/pnl_statement.html',
            context=context,
            filename='test_pnl'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Check PDF signature bytes %PDF
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 1000)

    def test_export_report_to_excel(self):
        """Test openpyxl creates valid Microsoft Excel spreadsheet."""
        headers = ['Period', 'Volume (L)', 'Revenue (NPR)']
        rows = [
            ['2026-11-20', 1200.50, 210000.00],
            ['2026-11-21', 1450.00, 253750.00],
        ]
        totals_row = ['TOTAL', 2650.50, 463750.00]

        response = export_report_to_excel(
            report_title='Daily Fuel Sales Test',
            headers=headers,
            rows=rows,
            totals_row=totals_row,
            filename='test_sales_excel'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('attachment; filename="test_sales_excel.xlsx"', response['Content-Disposition'])
        # Check standard ZIP archive signature (PK\x03\x04) for xlsx files
        self.assertTrue(response.content.startswith(b'PK\x03\x04'))

    # --------------------------------------------------------------------------
    # 6. HTTP Views and RBAC Permissions Tests
    # --------------------------------------------------------------------------
    def test_report_views_and_permissions(self):
        """Test Reports Hub, Sales Report, Inventory Reconciliation, Financial Statements views."""
        # 1. Operator can view sales report and inventory
        self.client.force_login(self.operator)
        res_hub = self.client.get(reverse('reports:hub'))
        self.assertEqual(res_hub.status_code, 200)

        res_sales = self.client.get(reverse('reports:sales_report'))
        self.assertEqual(res_sales.status_code, 200)

        res_inv = self.client.get(reverse('reports:inventory_report'))
        self.assertEqual(res_inv.status_code, 200)

        # Operator redirected from Financial Statements (manager/owner only)
        res_fin_op = self.client.get(reverse('reports:financial_statements'))
        self.assertEqual(res_fin_op.status_code, 302)
        self.assertIn(reverse('dashboard:index'), res_fin_op['Location'])

        # 2. Manager and Owner have access to Financial Statements
        self.client.force_login(self.manager)
        res_fin_mgr = self.client.get(reverse('reports:financial_statements'))
        self.assertEqual(res_fin_mgr.status_code, 200)

        # Balance Sheet tab
        res_fin_bs = self.client.get(reverse('reports:financial_statements') + '?tab=balance_sheet')
        self.assertEqual(res_fin_bs.status_code, 200)

        # Trial Balance tab
        res_fin_tb = self.client.get(reverse('reports:financial_statements') + '?tab=trial_balance')
        self.assertEqual(res_fin_tb.status_code, 200)

        # 3. Excel and PDF View downloads
        res_excel = self.client.get(reverse('reports:export_sales_excel') + '?group_by=daily')
        self.assertEqual(res_excel.status_code, 200)
        self.assertTrue(res_excel.content.startswith(b'PK\x03\x04'))

        res_pdf = self.client.get(reverse('reports:export_pnl_pdf'))
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(res_pdf.content.startswith(b'%PDF'))
