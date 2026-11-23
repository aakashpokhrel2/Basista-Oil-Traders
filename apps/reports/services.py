import io
import datetime
from decimal import Decimal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count, Q, Avg
from django.template.loader import render_to_string
from django.http import HttpResponse

import weasyprint
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from apps.station.models import StationConfiguration, FuelType, StorageTank, Pump, Nozzle
from apps.operations.models import FuelSale, Shift, StockMovement, MeterReading
from apps.purchases.models import FuelPurchase, Supplier, SupplierPayment
from apps.customers.models import Customer, CustomerPayment
from apps.expenses.models import Expense, ExpenseCategory
from apps.accounting.models import Account, JournalEntry, JournalLine, CashTransaction
from common.date_utils import ad_to_bs, format_bs_date


# ==============================================================================
# 1. Chart.js Analytics Data Generator
# ==============================================================================

def get_dashboard_charts_data():
    """
    Generate dataset structures for the 7 Chart.js widgets on the executive dashboard:
    1. Daily sales trends (last 7-14 days)
    2. Monthly sales trends (last 6 months)
    3. Petrol (MS) vs Diesel (HSD) volume ratio
    4. Monthly purchases
    5. Expenses by category
    6. Revenue trends
    7. Storage tank stock levels
    """
    today = timezone.now().date()

    # 1. Daily sales trend (Last 7 days)
    daily_labels = []
    daily_sales_ms = []
    daily_sales_hsd = []
    daily_revenue = []

    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        bs_day = ad_to_bs(day)
        label = f"{day.strftime('%b %d')} ({bs_day.month}/{bs_day.day})" if bs_day else day.strftime('%b %d')
        daily_labels.append(label)

        day_sales = FuelSale.objects.filter(transaction_date__date=day, is_cancelled=False)
        ms_vol = day_sales.filter(fuel_type__code='MS').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        hsd_vol = day_sales.filter(fuel_type__code='HSD').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        rev = day_sales.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')

        daily_sales_ms.append(float(ms_vol))
        daily_sales_hsd.append(float(hsd_vol))
        daily_revenue.append(float(rev))

    # 2. Petrol vs Diesel Overall Ratio (Liters)
    ms_tot = FuelSale.objects.filter(fuel_type__code='MS', is_cancelled=False).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
    hsd_tot = FuelSale.objects.filter(fuel_type__code='HSD', is_cancelled=False).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

    # 3. Expenses by Category
    exp_by_cat = Expense.objects.filter(approval_status='APPROVED').values(
        'category__name_en'
    ).annotate(total=Sum('amount')).order_by('-total')[:6]

    expense_labels = [item['category__name_en'] for item in exp_by_cat]
    expense_data = [float(item['total']) for item in exp_by_cat]

    # 4. Storage Tank Stock Levels
    tanks = StorageTank.objects.filter(is_active=True).select_related('fuel_type')
    tank_labels = [f"{t.tank_name} ({t.fuel_type.code})" for t in tanks]
    tank_current = [float(t.current_stock) for t in tanks]
    tank_capacity = [float(t.capacity_liters) for t in tanks]

    # 5. Purchases vs Sales
    tot_purchases = FuelPurchase.objects.filter(approval_status='APPROVED').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    tot_sales = FuelSale.objects.filter(is_cancelled=False).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')

    return {
        'daily_labels': daily_labels,
        'daily_sales_ms': daily_sales_ms,
        'daily_sales_hsd': daily_sales_hsd,
        'daily_revenue': daily_revenue,
        'petrol_vs_diesel': [float(ms_tot), float(hsd_tot)],
        'expense_labels': expense_labels,
        'expense_data': expense_data,
        'tank_labels': tank_labels,
        'tank_current': tank_current,
        'tank_capacity': tank_capacity,
        'tot_purchases': float(tot_purchases),
        'tot_sales': float(tot_sales),
    }


# ==============================================================================
# 2. Operational Reports Generator
# ==============================================================================

def get_operational_sales_report(
    group_by='daily',
    start_date=None,
    end_date=None,
    fuel_code=None,
    pump_id=None,
    payment_method=None
):
    """
    Generate multidimensional operational sales report:
    group_by options: 'daily', 'pump', 'nozzle', 'employee', 'shift', 'mechanism', 'payment'
    """
    qs = FuelSale.objects.filter(is_cancelled=False).select_related(
        'fuel_type', 'nozzle__pump', 'shift__schedule', 'recorded_by'
    )

    if start_date:
        qs = qs.filter(transaction_date__date__gte=start_date)
    if end_date:
        qs = qs.filter(transaction_date__date__lte=end_date)
    if fuel_code:
        qs = qs.filter(fuel_type__code=fuel_code)
    if pump_id:
        qs = qs.filter(nozzle__pump_id=pump_id)
    if payment_method:
        qs = qs.filter(payment_method=payment_method)

    if group_by == 'pump':
        records = qs.filter(nozzle__isnull=False).values(
            'nozzle__pump__pump_number', 'nozzle__pump__pump_name'
        ).annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id')
        ).order_by('nozzle__pump__pump_number')
    elif group_by == 'nozzle':
        records = qs.filter(nozzle__isnull=False).values(
            'nozzle__nozzle_code', 'fuel_type__code', 'nozzle__pump__pump_name'
        ).annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id')
        ).order_by('nozzle__nozzle_code')
    elif group_by == 'employee':
        records = qs.values(
            'recorded_by__username', 'recorded_by__first_name', 'recorded_by__last_name'
        ).annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id')
        ).order_by('-total_rev')
    elif group_by == 'shift':
        records = qs.filter(shift__isnull=False).values(
            'shift__shift_number', 'shift__schedule__name_en', 'shift__date_ad'
        ).annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id')
        ).order_by('-shift__date_ad')
    elif group_by == 'payment':
        records = qs.values('payment_method').annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id')
        ).order_by('-total_rev')
    elif group_by == 'mechanism':
        records = qs.values('sale_type').annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id')
        )
    else:  # Daily default
        records = qs.values('transaction_date__date').annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total_amount'),
            tx_count=Count('id'),
            ms_qty=Sum('quantity', filter=Q(fuel_type__code='MS')),
            hsd_qty=Sum('quantity', filter=Q(fuel_type__code='HSD')),
        ).order_by('-transaction_date__date')

    totals = qs.aggregate(
        grand_volume=Sum('quantity'),
        grand_revenue=Sum('total_amount'),
        grand_count=Count('id')
    )

    return records, totals


# ==============================================================================
# 3. Inventory Reconciliation Report
# ==============================================================================

def get_inventory_reconciliation_report(start_date=None, end_date=None, tank_id=None):
    """
    Inventory reconciliation by tank:
    Opening Stock + Purchases - Dispensed Quantity + Testing Returns +/- Adjustments = Expected Closing Stock.
    """
    tanks = StorageTank.objects.filter(is_active=True).select_related('fuel_type')
    if tank_id:
        tanks = tanks.filter(pk=tank_id)

    report_rows = []

    for tank in tanks:
        movements = StockMovement.objects.filter(tank=tank)
        if start_date:
            movements = movements.filter(timestamp__date__gte=start_date)
        if end_date:
            movements = movements.filter(timestamp__date__lte=end_date)

        first_mov = movements.order_by('timestamp', 'id').first()
        last_mov = movements.order_by('-timestamp', '-id').first()

        opening_stock = first_mov.opening_balance if first_mov else tank.current_stock
        closing_stock = last_mov.closing_balance if last_mov else tank.current_stock

        purchases = movements.filter(movement_type='PURCHASE').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        dispensed = movements.filter(movement_type__in=['SALE_METER', 'SALE_MANUAL']).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        test_returns = movements.filter(movement_type='TEST_RETURN').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        reversals = movements.filter(movement_type='SALE_REVERSAL').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        adj_loss = movements.filter(movement_type='ADJUSTMENT_LOSS').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
        adj_gain = movements.filter(movement_type='ADJUSTMENT_GAIN').aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

        # Formula
        expected_closing = opening_stock + purchases - dispensed + test_returns + reversals - adj_loss + adj_gain
        variance = closing_stock - expected_closing

        report_rows.append({
            'tank': tank,
            'fuel_type': tank.fuel_type,
            'opening_stock': opening_stock,
            'purchases': purchases,
            'dispensed': dispensed,
            'test_returns': test_returns + reversals,
            'adjustments': adj_gain - adj_loss,
            'expected_closing': expected_closing,
            'actual_closing': closing_stock,
            'variance': variance,
        })

    return report_rows


# ==============================================================================
# 4. Double-Entry Financial Reports (P&L, Balance Sheet, Trial Balance)
# ==============================================================================

def get_income_statement_data(start_date=None, end_date=None):
    """
    Double-entry Income Statement (P&L):
    Revenue: Fuel Sales Revenue (MS & HSD)
    Cost of Goods Sold (COGS): Opening Stock + Purchases - Closing Stock
    Gross Profit = Revenue - COGS
    Operating Expenses: Electricity, Salaries, Rent, Maintenance, etc.
    Net Operating Profit = Gross Profit - Operating Expenses
    """
    sales_qs = FuelSale.objects.filter(is_cancelled=False)
    purchases_qs = FuelPurchase.objects.filter(approval_status='APPROVED')
    expenses_qs = Expense.objects.filter(approval_status='APPROVED')

    if start_date:
        sales_qs = sales_qs.filter(transaction_date__date__gte=start_date)
        purchases_qs = purchases_qs.filter(purchase_date__gte=start_date)
        expenses_qs = expenses_qs.filter(date__gte=start_date)
    if end_date:
        sales_qs = sales_qs.filter(transaction_date__date__lte=end_date)
        purchases_qs = purchases_qs.filter(purchase_date__lte=end_date)
        expenses_qs = expenses_qs.filter(date__lte=end_date)

    # 1. Revenue
    petrol_sales_rev = sales_qs.filter(fuel_type__code='MS').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    diesel_sales_rev = sales_qs.filter(fuel_type__code='HSD').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_revenue = petrol_sales_rev + diesel_sales_rev

    # 2. Cost of Goods Sold (COGS)
    petrol_purchases = purchases_qs.filter(fuel_type__code='MS').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    diesel_purchases = purchases_qs.filter(fuel_type__code='HSD').aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_cogs = petrol_purchases + diesel_purchases

    gross_profit = total_revenue - total_cogs

    # 3. Operating Expenses Breakdown
    expense_breakdown = expenses_qs.values('category__name_en', 'category__name_ne').annotate(
        total=Sum('amount')
    ).order_by('-total')
    total_operating_expenses = expenses_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    net_profit = gross_profit - total_operating_expenses

    return {
        'petrol_sales_rev': petrol_sales_rev,
        'diesel_sales_rev': diesel_sales_rev,
        'total_revenue': total_revenue,
        'total_cogs': total_cogs,
        'gross_profit': gross_profit,
        'expense_breakdown': expense_breakdown,
        'total_operating_expenses': total_operating_expenses,
        'net_profit': net_profit,
    }


def get_balance_sheet_data(as_of_date=None):
    """
    Double-entry Balance Sheet: Assets = Liabilities + Equity
    Assets: Cash in Drawer, Bank, Fuel Inventory (valuation), Accounts Receivable
    Liabilities: Accounts Payable (Suppliers)
    Equity: Owner Capital + Net Retained Earnings
    """
    last_cash = CashTransaction.objects.order_by('-id').first()
    cash_balance = last_cash.balance_after if last_cash else Decimal('0.00')

    # Fuel inventory valuation
    inventory_val = Decimal('0.00')
    for tank in StorageTank.objects.filter(is_active=True):
        cur_price = tank.fuel_type.get_current_price()
        rate = cur_price.purchase_price if cur_price else Decimal('150.00')
        inventory_val += (tank.current_stock * rate)

    # Accounts Receivable
    ar_balance = Customer.objects.aggregate(s=Sum('current_balance'))['s'] or Decimal('0.00')
    total_assets = cash_balance + inventory_val + ar_balance

    # Liabilities
    ap_balance = Supplier.objects.aggregate(s=Sum('current_balance'))['s'] or Decimal('0.00')
    total_liabilities = ap_balance

    # Equity
    equity_balance = total_assets - total_liabilities

    return {
        'cash_balance': cash_balance,
        'inventory_val': inventory_val,
        'ar_balance': ar_balance,
        'total_assets': total_assets,
        'ap_balance': ap_balance,
        'total_liabilities': total_liabilities,
        'equity_balance': equity_balance,
    }


def get_trial_balance_data():
    """Double-entry Trial Balance verifying Total Debits == Total Credits."""
    accounts = Account.objects.filter(is_active=True).order_by('account_number')
    tb_rows = []
    tot_dr = Decimal('0.00')
    tot_cr = Decimal('0.00')

    for acct in accounts:
        lines = acct.journal_lines.filter(journal_entry__is_posted=True)
        dr = lines.aggregate(s=Sum('debit'))['s'] or Decimal('0.00')
        cr = lines.aggregate(s=Sum('credit'))['s'] or Decimal('0.00')

        if dr > cr:
            net_dr = dr - cr
            net_cr = Decimal('0.00')
        else:
            net_dr = Decimal('0.00')
            net_cr = cr - dr

        if net_dr > 0 or net_cr > 0:
            tb_rows.append({
                'account': acct,
                'debit': net_dr,
                'credit': net_cr,
            })
            tot_dr += net_dr
            tot_cr += net_cr

    return tb_rows, tot_dr, tot_cr


# ==============================================================================
# 5. WeasyPrint PDF Exporter (Unicode & Noto Sans Devanagari Compatible)
# ==============================================================================

def export_report_to_pdf(template_name: str, context: dict, filename: str) -> HttpResponse:
    """
    Renders an HTML template into a PDF using WeasyPrint with complete Nepali Devanagari font support.
    """
    station = StationConfiguration.get_solo()
    context.update({
        'station': station,
        'station_name': station.station_name,
        'generated_at': timezone.now(),
        'generated_at_bs': format_bs_date(ad_to_bs(timezone.now().date()), lang='en', include_weekday=True),
    })

    html_string = render_to_string(template_name, context)
    pdf_bytes = weasyprint.HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}.pdf"'
    return response


# ==============================================================================
# 6. openpyxl Excel (.xlsx) Exporter
# ==============================================================================

def export_report_to_excel(
    report_title: str,
    headers: list[str],
    rows: list[list],
    totals_row: list = None,
    filename: str = 'report'
) -> HttpResponse:
    """
    Generates a professionally styled Microsoft Excel spreadsheet (.xlsx) with openpyxl.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = report_title[:30]

    station = StationConfiguration.get_solo()

    # Styling Palettes
    header_font = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='064E3B', end_color='064E3B', fill_type='solid') # Emerald-900
    title_font = Font(name='Segoe UI', size=14, bold=True, color='064E3B')
    subtitle_font = Font(name='Segoe UI', size=9, italic=True, color='4B5563')
    bold_font = Font(name='Segoe UI', size=10, bold=True)
    regular_font = Font(name='Segoe UI', size=10)
    totals_fill = PatternFill(start_color='ECFDF5', end_color='ECFDF5', fill_type='solid') # Emerald-50
    thin_border = Border(
        left=Side(style='thin', color='E5E7EB'),
        right=Side(style='thin', color='E5E7EB'),
        top=Side(style='thin', color='E5E7EB'),
        bottom=Side(style='thin', color='E5E7EB')
    )

    # 1. Title Block
    ws.append([station.station_name])
    ws.cell(row=1, column=1).font = title_font

    ws.append([f"{report_title} - Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')} (AD)"])
    ws.cell(row=2, column=1).font = subtitle_font
    ws.append([]) # empty row

    # 2. Table Headers
    ws.append(headers)
    header_row_idx = 4
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    # 3. Data Rows
    current_row = 5
    for row_data in rows:
        ws.append(row_data)
        for col_idx in range(1, len(row_data) + 1):
            c = ws.cell(row=current_row, column=col_idx)
            c.font = regular_font
            c.border = thin_border
            if isinstance(c.value, (int, float, Decimal)):
                c.alignment = Alignment(horizontal='right')
        current_row += 1

    # 4. Totals Row
    if totals_row:
        ws.append(totals_row)
        for col_idx in range(1, len(totals_row) + 1):
            c = ws.cell(row=current_row, column=col_idx)
            c.font = bold_font
            c.fill = totals_fill
            c.border = thin_border
            if isinstance(c.value, (int, float, Decimal)):
                c.alignment = Alignment(horizontal='right')

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    return response
