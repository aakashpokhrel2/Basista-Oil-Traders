import json
from decimal import Decimal
import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.utils.translation import gettext_lazy as _

from apps.station.models import StationConfiguration, FuelType, StorageTank, Pump, Nozzle, FuelPrice
from apps.operations.models import FuelSale, Shift, MeterReading
from apps.purchases.models import FuelPurchase, Supplier
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.accounting.models import CashTransaction
from apps.reports.services import get_dashboard_charts_data
from common.date_utils import ad_to_bs, format_bs_date


@login_required
def dashboard_view(request):
    """
    Main station operations and business analytics executive dashboard.
    Displays live metric strips, tank stock level gauges, customer credit,
    supplier payables, drawer cash balance, and 7 Chart.js visual analytics.
    """
    now = timezone.localtime(timezone.now())
    today = now.date()
    today_bs = ad_to_bs(today)

    # 1. Today's Fuel Sales Metrics
    today_sales = FuelSale.objects.filter(transaction_date__date=today, is_cancelled=False)
    today_rev = today_sales.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    today_litres = today_sales.aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

    today_ms = today_sales.filter(fuel_type__code='MS').aggregate(
        qty=Sum('quantity'), rev=Sum('total_amount')
    )
    today_hsd = today_sales.filter(fuel_type__code='HSD').aggregate(
        qty=Sum('quantity'), rev=Sum('total_amount')
    )

    # 2. Financial & Credit Totals
    total_purchases = FuelPurchase.objects.filter(approval_status='APPROVED').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_expenses = Expense.objects.filter(approval_status='APPROVED').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    customer_credit = Customer.objects.aggregate(s=Sum('current_balance'))['s'] or Decimal('0.00')
    supplier_payable = Supplier.objects.aggregate(s=Sum('current_balance'))['s'] or Decimal('0.00')

    # 3. Cash in Drawer
    last_cash = CashTransaction.objects.order_by('-id').first()
    cash_balance = last_cash.balance_after if last_cash else Decimal('0.00')

    # 4. Storage Tanks Status
    all_tanks = StorageTank.objects.select_related('fuel_type').filter(is_active=True).order_by('tank_number')

    # 5. Active Shift
    active_shift = Shift.objects.filter(status='OPEN').first()

    # 6. Fuel Prices
    ms_fuel = FuelType.objects.filter(code='MS').first()
    hsd_fuel = FuelType.objects.filter(code='HSD').first()
    petrol_price = ms_fuel.get_current_price() if ms_fuel else None
    diesel_price = hsd_fuel.get_current_price() if hsd_fuel else None

    # 7. Chart.js Data
    charts_data = get_dashboard_charts_data()

    context = {
        'page_title': _('Station Executive Dashboard'),
        'today_rev': today_rev,
        'today_litres': today_litres,
        'today_ms': today_ms,
        'today_hsd': today_hsd,
        'total_purchases': total_purchases,
        'total_expenses': total_expenses,
        'customer_credit': customer_credit,
        'supplier_payable': supplier_payable,
        'cash_balance': cash_balance,
        'all_tanks': all_tanks,
        'active_shift': active_shift,
        'petrol_price': petrol_price,
        'diesel_price': diesel_price,
        'today_bs_full': format_bs_date(today_bs, lang=request.LANGUAGE_CODE, include_weekday=True),
        'today_ad_full': now.strftime('%A, %B %d, %Y'),
        'charts_data_json': json.dumps(charts_data),
    }
    return render(request, 'dashboard/index.html', context)
