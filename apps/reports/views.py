import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse

from apps.reports.services import (
    get_operational_sales_report,
    get_inventory_reconciliation_report,
    get_income_statement_data,
    get_balance_sheet_data,
    get_trial_balance_data,
    export_report_to_pdf,
    export_report_to_excel,
)
from apps.station.models import FuelType, StorageTank, Pump, Nozzle
from apps.operations.models import FuelSale
from common.permissions import role_required
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT


@login_required
def reports_hub_view(request):
    """Central reports and analytics portal."""
    return render(request, 'reports/hub.html', {
        'title': _('Reports & Business Analytics')
    })


@login_required
def sales_report_view(request):
    """
    Multidimensional operational sales report:
    Group by: Daily, Pump, Nozzle, Employee, Shift, Mechanism, Payment.
    """
    group_by = request.GET.get('group_by', 'daily')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    fuel_code = request.GET.get('fuel')
    payment_method = request.GET.get('payment')

    records, totals = get_operational_sales_report(
        group_by=group_by,
        start_date=start_date,
        end_date=end_date,
        fuel_code=fuel_code,
        payment_method=payment_method
    )

    context = {
        'title': _('Operational Fuel Sales Report'),
        'group_by': group_by,
        'records': records,
        'totals': totals,
        'start_date': start_date,
        'end_date': end_date,
        'fuels': FuelType.objects.filter(is_active=True),
        'selected_fuel': fuel_code,
        'selected_payment': payment_method,
    }
    return render(request, 'reports/sales_report.html', context)


@login_required
def inventory_report_view(request):
    """Underground storage tank stock reconciliation report."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    tank_id = request.GET.get('tank')

    report_rows = get_inventory_reconciliation_report(
        start_date=start_date,
        end_date=end_date,
        tank_id=tank_id
    )

    context = {
        'title': _('Underground Fuel Inventory Reconciliation'),
        'report_rows': report_rows,
        'tanks': StorageTank.objects.filter(is_active=True),
        'start_date': start_date,
        'end_date': end_date,
        'selected_tank': tank_id,
    }
    return render(request, 'reports/inventory_report.html', context)


@role_required([ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT])
def financial_statements_view(request):
    """
    Double-entry financial statements:
    - Income Statement (P&L with Cost of Goods Sold)
    - Balance Sheet (Assets = Liabilities + Equity)
    - Trial Balance (Total Debits == Total Credits)
    """
    tab = request.GET.get('tab', 'pnl')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    context = {
        'title': _('Financial Statements & Double-Entry Reports'),
        'tab': tab,
        'start_date': start_date,
        'end_date': end_date,
    }

    if tab == 'pnl':
        context['pnl'] = get_income_statement_data(start_date=start_date, end_date=end_date)
    elif tab == 'balance_sheet':
        context['bs'] = get_balance_sheet_data()
    elif tab == 'trial_balance':
        tb_rows, tot_dr, tot_cr = get_trial_balance_data()
        context['tb_rows'] = tb_rows
        context['tot_dr'] = tot_dr
        context['tot_cr'] = tot_cr

    return render(request, 'reports/financial_statements.html', context)


# ==============================================================================
# Exports: WeasyPrint PDF & openpyxl Excel
# ==============================================================================

@login_required
def export_sales_excel_view(request):
    """Export sales data to Excel .xlsx using openpyxl."""
    group_by = request.GET.get('group_by', 'daily')
    records, totals = get_operational_sales_report(group_by=group_by)

    headers = ['Period / Label', 'Fuel Volume (Litres)', 'Sales Revenue (NPR)', 'Invoices']
    rows = []

    for r in records:
        if group_by == 'pump':
            label = f"Pump #{r['nozzle__pump__pump_number']} - {r['nozzle__pump__pump_name']}"
        elif group_by == 'nozzle':
            label = f"Nozzle {r['nozzle__nozzle_code']} ({r['fuel_type__code']})"
        elif group_by == 'employee':
            label = r['recorded_by__username']
        elif group_by == 'shift':
            label = f"Shift #{r['shift__shift_number']} ({r['shift__schedule__name_en']})"
        elif group_by == 'payment':
            label = r['payment_method']
        elif group_by == 'mechanism':
            label = r['sale_type']
        else:
            label = str(r['transaction_date__date'])

        rows.append([
            label,
            float(r['total_qty']),
            float(r['total_rev']),
            r['tx_count']
        ])

    totals_row = [
        'GRAND TOTAL',
        float(totals['grand_volume'] or 0),
        float(totals['grand_revenue'] or 0),
        totals['grand_count'] or 0
    ]

    return export_report_to_excel(
        report_title=f"Sales Report ({group_by.capitalize()})",
        headers=headers,
        rows=rows,
        totals_row=totals_row,
        filename=f"sales_report_{group_by}_{timezone.now().strftime('%Y%m%d')}"
    )


@role_required([ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT])
def export_pnl_pdf_view(request):
    """Export Income Statement (P&L) to PDF via WeasyPrint."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    pnl = get_income_statement_data(start_date=start_date, end_date=end_date)

    context = {
        'pnl': pnl,
        'start_date': start_date,
        'end_date': end_date,
        'title': _('Profit & Loss Statement (Income Statement)')
    }
    return export_report_to_pdf(
        template_name='reports/pdf/pnl_statement.html',
        context=context,
        filename=f"pnl_statement_{timezone.now().strftime('%Y%m%d')}"
    )
