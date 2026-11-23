import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import FinancialPeriod, Account, CashTransaction
from apps.accounting.services import (
    get_or_create_default_accounts, record_cash_transaction, create_journal_entry
)
from apps.purchases.models import Supplier, FuelPurchase, SupplierPayment
from apps.purchases.services import approve_fuel_purchase, record_supplier_payment
from apps.customers.models import Customer, CustomerPayment
from apps.customers.services import record_customer_payment
from apps.expenses.models import ExpenseCategory, Expense
from apps.expenses.services import seed_default_expense_categories, record_and_approve_expense
from apps.station.models import FuelType, StorageTank

User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic sample data for Phase 4 (Suppliers, Purchases, Customers, Expenses, Accounting)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Phase 4 data..."))

        owner = User.objects.filter(role='OWNER').first() or User.objects.filter(is_superuser=True).first()
        manager = User.objects.filter(role='MANAGER').first() or owner
        accountant = User.objects.filter(role='ACCOUNTANT').first() or manager

        # 1. Chart of Accounts & Expense Categories
        get_or_create_default_accounts()
        seed_default_expense_categories()

        # 2. Financial Periods
        FinancialPeriod.objects.get_or_create(
            fiscal_year_bs="2082/83",
            defaults={
                'name': "Fiscal Year 2082/83",
                'start_date_ad': datetime.date(2025, 7, 16),
                'end_date_ad': datetime.date(2026, 7, 15),
                'is_active': True,
                'is_closed': False,
            }
        )

        # 3. Initial Cash Float in Drawer
        if not CashTransaction.objects.exists():
            record_cash_transaction(
                transaction_type='INFLOW',
                source_category='CAPITAL_INJECTION',
                amount=Decimal('100000.00'),
                performed_by=owner,
                description="Opening Capital & Drawer Float from Owner",
                reference_type='CapitalInjection',
                reference_id='CAP-001'
            )

        # 4. Suppliers
        noc_amlekhgunj, _ = Supplier.objects.get_or_create(
            name="Nepal Oil Corporation - Amlekhgunj Depot",
            defaults={
                'contact_person': "Ram Prasad Sharma (Depot Chief)",
                'phone': "051-521122",
                'email': "amlekhgunj@noc.org.np",
                'address': "Amlekhgunj, Bara, Madhesh Province",
                'pan_vat_number': "100023456",
                'opening_payable_balance': Decimal('250000.00'),
                'current_balance': Decimal('250000.00'),
                'status': 'ACTIVE',
            }
        )

        noc_birgunj, _ = Supplier.objects.get_or_create(
            name="Nepal Oil Corporation - Birgunj Branch",
            defaults={
                'contact_person': "Bikash Adhikari",
                'phone': "051-523344",
                'email': "birgunj@noc.org.np",
                'address': "Dry Port Road, Birgunj",
                'pan_vat_number': "100023457",
                'opening_payable_balance': Decimal('0.00'),
                'current_balance': Decimal('0.00'),
                'status': 'ACTIVE',
            }
        )

        # 5. Purchases
        ms = FuelType.objects.filter(code='MS').first()
        hsd = FuelType.objects.filter(code='HSD').first()
        tank_ms = StorageTank.objects.filter(fuel_type=ms).first()
        tank_hsd = StorageTank.objects.filter(fuel_type=hsd).first()

        if ms and tank_ms:
            p1, is_p1_new = FuelPurchase.objects.get_or_create(
                supplier=noc_amlekhgunj,
                invoice_number="NOC-2082-8492",
                defaults={
                    'purchase_date': timezone.now().date() - datetime.timedelta(days=3),
                    'fuel_type': ms,
                    'receiving_tank': tank_ms,
                    'delivered_quantity': Decimal('4000.00'),
                    'purchase_price': Decimal('155.00'),
                    'total_amount': Decimal('620000.00'),
                    'paid_amount': Decimal('400000.00'),
                    'payment_status': 'PARTIAL',
                    'approval_status': 'PENDING',
                    'tanker_number': "Na 7 Kha 4521",
                    'driver_name': "Bishnu Bahadur Thapa",
                    'created_by': accountant,
                }
            )
            if is_p1_new:
                approve_fuel_purchase(p1, approved_by=manager)

        if hsd and tank_hsd:
            p2, is_p2_new = FuelPurchase.objects.get_or_create(
                supplier=noc_birgunj,
                invoice_number="NOC-2082-9102",
                defaults={
                    'purchase_date': timezone.now().date() - datetime.timedelta(days=1),
                    'fuel_type': hsd,
                    'receiving_tank': tank_hsd,
                    'delivered_quantity': Decimal('6000.00'),
                    'purchase_price': Decimal('135.00'),
                    'total_amount': Decimal('810000.00'),
                    'paid_amount': Decimal('0.00'),
                    'payment_status': 'UNPAID',
                    'approval_status': 'PENDING',
                    'tanker_number': "Na 8 Kha 7812",
                    'driver_name': "Krishna Kumar Chaudhary",
                    'created_by': accountant,
                }
            )
            if is_p2_new:
                approve_fuel_purchase(p2, approved_by=manager)

        # 6. Supplier Partial Payment
        if not SupplierPayment.objects.exists():
            record_supplier_payment(
                supplier=noc_amlekhgunj,
                amount=Decimal('500000.00'),
                payment_method='BANK_TRANSFER',
                payment_reference='IPS-NOC-992182',
                notes='Partial tanker bill payment via ConnectIPS to NOC Amlekhgunj',
                recorded_by=accountant
            )

        # 7. Customers
        c1, _ = Customer.objects.get_or_create(
            name="Bagmati Yatayat Sewa Samiti",
            defaults={
                'contact_person': "Narayan Prasad Kandel (President)",
                'phone': "9851023456",
                'email': "bagmati.transport@gmail.com",
                'address': "Hetauda-Kathmandu Route Fleet",
                'pan_vat_number': "302918273",
                'credit_limit': Decimal('500000.00'),
                'current_balance': Decimal('145000.00'),
                'status': 'ACTIVE',
            }
        )

        c2, _ = Customer.objects.get_or_create(
            name="Everest Highway Builders Pvt Ltd",
            defaults={
                'contact_person': "Er. Dinesh Shrestha",
                'phone': "9841876543",
                'email': "everest.builders@gmail.com",
                'address': "Narayanghat-Butwal Road Project",
                'pan_vat_number': "601928374",
                'credit_limit': Decimal('300000.00'),
                'current_balance': Decimal('68000.00'),
                'status': 'ACTIVE',
            }
        )

        # 8. Customer Collection
        if not CustomerPayment.objects.exists():
            record_customer_payment(
                customer=c1,
                amount=Decimal('45000.00'),
                payment_method='BANK_TRANSFER',
                reference_number='NIBL-TXN-44129',
                notes='Monthly diesel credit installment via Nepal Investment Mega Bank',
                recorded_by=accountant
            )

        # 9. Expenses
        if not Expense.objects.exists():
            cat_elec = ExpenseCategory.objects.filter(code='EXP_ELEC').first()
            cat_sal = ExpenseCategory.objects.filter(code='EXP_SAL').first()
            cat_repair = ExpenseCategory.objects.filter(code='EXP_REPAIR').first()
            cat_office = ExpenseCategory.objects.filter(code='EXP_OFFICE').first()

            if cat_elec:
                record_and_approve_expense(
                    category=cat_elec,
                    amount=Decimal('18500.00'),
                    description="Nepal Electricity Authority (NEA) station monthly tariff bill",
                    payment_method='BANK_TRANSFER',
                    payee_name="Nepal Electricity Authority, Simara Branch",
                    reference_number="NEA-2082-9981",
                    recorded_by=accountant
                )

            if cat_repair:
                record_and_approve_expense(
                    category=cat_repair,
                    amount=Decimal('4500.00'),
                    description="Dispenser Island 1 nozzle calibration & O-ring seal replacement",
                    payment_method='CASH',
                    payee_name="Nepal Petroleum Tech Services",
                    reference_number="BILL-7712",
                    recorded_by=accountant
                )

            if cat_office:
                record_and_approve_expense(
                    category=cat_office,
                    amount=Decimal('2200.00'),
                    description="Thermal paper rolls for billing printer and drinking water jars",
                    payment_method='CASH',
                    payee_name="Om Stationery & Drinking Water",
                    reference_number="VOUCHER-01",
                    recorded_by=accountant
                )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Phase 4 sample data!"))
