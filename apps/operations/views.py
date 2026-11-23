"""
Views for Shifts, Meter Readings, Fuel Sales Register, Auditable Stock Ledger, and Sales Reconciliation.
"""

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, CreateView, DetailView

from apps.station.models import FuelType, StorageTank, Pump, Nozzle, FuelPrice
from apps.operations.models import Shift, ShiftSchedule, MeterReading, FuelSale, StockMovement
from apps.operations.forms import (
    ShiftOpenForm,
    ShiftCloseForm,
    MeterReadingForm,
    ManualSaleForm,
    SaleCancellationForm,
    StockAdjustmentForm,
)
from apps.operations.services import (
    record_stock_movement,
    record_manual_sale,
    cancel_fuel_sale,
    process_meter_reading,
    close_shift_session,
)
from common.permissions import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    ROLE_CASHIER,
    ROLE_PUMP_OPERATOR,
    RoleRequiredMixin,
    manager_or_owner_required,
)
from common.date_utils import ad_to_bs, format_bs_date


# ==============================================================================
# 1. Shift Management Views
# ==============================================================================

class ShiftListView(RoleRequiredMixin, ListView):
    model = Shift
    template_name = 'operations/shift_list.html'
    context_object_name = 'shifts'
    paginate_by = 15
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER, ROLE_PUMP_OPERATOR]

    def get_queryset(self):
        qs = Shift.objects.select_related('schedule', 'supervisor', 'approved_by').prefetch_related('operators')
        status = self.request.GET.get('status', '').strip()
        date_q = self.request.GET.get('date', '').strip()

        if status:
            qs = qs.filter(status=status)
        if date_q:
            qs = qs.filter(date_ad=date_q)

        return qs.order_by('-opening_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_shift'] = Shift.objects.filter(status='OPEN').first()
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_date'] = self.request.GET.get('date', '')
        return context


@login_required
def shift_open_view(request):
    """Open new operational shift."""
    if not (request.user.is_owner or request.user.is_manager):
        messages.error(request, _("Only Station Managers or Owners can open a new shift."))
        return redirect('operations:shift_list')

    # Check if an open shift already exists
    active_shift = Shift.objects.filter(status='OPEN').first()
    if active_shift:
        messages.warning(
            request,
            _("Shift '%(shift)s' is currently OPEN. Close it before opening a new shift.") % {'shift': active_shift.shift_number}
        )
        return redirect('operations:shift_detail', pk=active_shift.pk)

    if request.method == 'POST':
        form = ShiftOpenForm(request.POST)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.date_ad = timezone.now().date()
            bs_obj = ad_to_bs(shift.date_ad)
            shift.date_bs = f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}"
            shift.save()
            form.save_m2m()

            messages.success(request, _("Shift '%(shift)s' opened successfully.") % {'shift': shift.shift_number})
            return redirect('operations:shift_detail', pk=shift.pk)
    else:
        form = ShiftOpenForm(initial={'supervisor': request.user})

    context = {
        'title': _('Open New Shift Session'),
        'form': form,
    }
    return render(request, 'operations/shift_form.html', context)


@login_required
def shift_detail_view(request, pk):
    """Shift overview: nozzle readings, sales register, cash variance reconciliation."""
    shift = get_object_or_404(Shift.objects.select_related('schedule', 'supervisor', 'approved_by').prefetch_related('operators'), pk=pk)

    readings = shift.meter_readings.select_related('nozzle__fuel_type', 'nozzle__pump', 'recorded_by').all()
    sales = shift.sales.select_related('fuel_type', 'nozzle', 'recorded_by').filter(is_cancelled=False).order_by('-transaction_date')

    # Aggregates
    summary = sales.aggregate(
        total_qty=Sum('quantity'),
        total_rev=Sum('total_amount'),
        cash_rev=Sum('total_amount', filter=Q(payment_method='CASH')),
        credit_rev=Sum('total_amount', filter=Q(payment_method='CREDIT')),
        bank_rev=Sum('total_amount', filter=Q(payment_method__in=['BANK_TRANSFER', 'QR_FONEPAY'])),
    )

    all_active_nozzles = Nozzle.objects.filter(status='ACTIVE')
    read_nozzle_ids = set(readings.values_list('nozzle_id', flat=True))
    unread_nozzles = all_active_nozzles.exclude(id__in=read_nozzle_ids)

    context = {
        'shift': shift,
        'readings': readings,
        'sales': sales[:10],
        'total_sales_count': sales.count(),
        'summary': summary,
        'unread_nozzles': unread_nozzles,
        'all_readings_entered': unread_nozzles.count() == 0,
    }
    return render(request, 'operations/shift_detail.html', context)


@login_required
def shift_close_view(request, pk):
    """Close shift and enter physical counted cash."""
    shift = get_object_or_404(Shift, pk=pk)
    if shift.status != 'OPEN':
        messages.info(request, _("This shift is already closed."))
        return redirect('operations:shift_detail', pk=shift.pk)

    if request.method == 'POST':
        form = ShiftCloseForm(request.POST, instance=shift)
        if form.is_valid():
            closing_cash = form.cleaned_data['closing_cash_balance']
            collected_cash = form.cleaned_data['actual_cash_collected']
            notes = form.cleaned_data['handover_notes']

            close_shift_session(
                shift=shift,
                closing_cash_counted=closing_cash,
                actual_cash_collected=collected_cash,
                handover_notes=notes
            )
            messages.success(request, _("Shift '%(num)s' closed successfully.") % {'num': shift.shift_number})
            return redirect('operations:shift_detail', pk=shift.pk)
    else:
        # Precalculate expected cash
        cash_sales = shift.sales.filter(is_cancelled=False, payment_method='CASH').aggregate(
            t=Sum('total_amount')
        )['t'] or Decimal('0.00')
        expected = shift.opening_cash_balance + cash_sales

        form = ShiftCloseForm(instance=shift, initial={
            'closing_cash_balance': expected,
            'actual_cash_collected': expected,
        })

    context = {
        'shift': shift,
        'form': form,
    }
    return render(request, 'operations/shift_close.html', context)


@manager_or_owner_required
def shift_approve_view(request, pk):
    """Reconcile and approve a closed shift."""
    shift = get_object_or_404(Shift, pk=pk)
    if shift.status == 'CLOSED':
        shift.status = 'APPROVED'
        shift.approved_by = request.user
        shift.approved_at = timezone.now()
        shift.save(update_fields=['status', 'approved_by', 'approved_at'])
        messages.success(request, _("Shift '%(num)s' has been approved and reconciled.") % {'num': shift.shift_number})
    else:
        messages.info(request, _("Shift is currently '%(st)s'.") % {'st': shift.get_status_display()})

    return redirect('operations:shift_detail', pk=shift.pk)


# ==============================================================================
# 2. Meter Readings Views
# ==============================================================================

class MeterReadingListView(RoleRequiredMixin, ListView):
    model = MeterReading
    template_name = 'operations/meter_reading_list.html'
    context_object_name = 'readings'
    paginate_by = 20
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER, ROLE_PUMP_OPERATOR]

    def get_queryset(self):
        qs = MeterReading.objects.select_related('nozzle__fuel_type', 'nozzle__pump', 'shift', 'recorded_by')
        shift_q = self.request.GET.get('shift', '').strip()
        nozzle_q = self.request.GET.get('nozzle', '').strip()

        if shift_q:
            qs = qs.filter(shift__shift_number__icontains=shift_q)
        if nozzle_q:
            qs = qs.filter(nozzle_id=nozzle_q)

        return qs.order_by('-reading_timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nozzles'] = Nozzle.objects.filter(status='ACTIVE')
        context['active_shift'] = Shift.objects.filter(status='OPEN').first()
        return context


@login_required
def meter_reading_create_view(request):
    """Log nozzle meter reading for active shift."""
    active_shift = Shift.objects.filter(status='OPEN').first()
    if not active_shift:
        messages.error(request, _("No active OPEN shift found! Please open a shift before logging meter readings."))
        return redirect('operations:shift_list')

    if request.method == 'POST':
        form = MeterReadingForm(request.POST, shift=active_shift)
        if form.is_valid():
            try:
                nozzle = form.cleaned_data['nozzle']
                closing_reading = form.cleaned_data['closing_meter_reading']
                test_qty = form.cleaned_data['test_dispense_quantity']
                is_rollover = form.cleaned_data['is_rollover']
                rollover_reason = form.cleaned_data['rollover_reason']

                process_meter_reading(
                    shift=active_shift,
                    nozzle=nozzle,
                    closing_reading=closing_reading,
                    recorded_by=request.user,
                    test_dispense_quantity=test_qty,
                    is_rollover=is_rollover,
                    rollover_reason=rollover_reason,
                    rollover_authorized_by=request.user if is_rollover else None,
                )
                messages.success(request, _("Meter reading for nozzle '%(code)s' recorded.") % {'code': nozzle.nozzle_code})
                return redirect('operations:shift_detail', pk=active_shift.pk)
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        nozzle_id = request.GET.get('nozzle')
        initial = {}
        if nozzle_id:
            try:
                nozzle = Nozzle.objects.get(pk=nozzle_id)
                initial['nozzle'] = nozzle
                initial['closing_meter_reading'] = nozzle.current_meter_reading
            except Nozzle.DoesNotExist:
                pass
        form = MeterReadingForm(shift=active_shift, initial=initial)

    context = {
        'title': _('Record Nozzle Meter Reading'),
        'form': form,
        'active_shift': active_shift,
    }
    return render(request, 'operations/meter_reading_form.html', context)


# ==============================================================================
# 3. Fuel Sales Register & Manual Sales
# ==============================================================================

class DailySalesRegisterView(RoleRequiredMixin, ListView):
    model = FuelSale
    template_name = 'operations/sales_register.html'
    context_object_name = 'sales'
    paginate_by = 25
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER]

    def get_queryset(self):
        qs = FuelSale.objects.select_related('fuel_type', 'nozzle', 'tank', 'shift', 'recorded_by')
        q = self.request.GET.get('q', '').strip()
        fuel_code = self.request.GET.get('fuel', '').strip()
        payment_method = self.request.GET.get('payment', '').strip()
        sale_type = self.request.GET.get('type', '').strip()
        date_q = self.request.GET.get('date', '').strip()

        if q:
            qs = qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer_name__icontains=q) |
                Q(vehicle_number__icontains=q)
            )
        if fuel_code:
            qs = qs.filter(fuel_type__code=fuel_code)
        if payment_method:
            qs = qs.filter(payment_method=payment_method)
        if sale_type:
            qs = qs.filter(sale_type=sale_type)
        if date_q:
            qs = qs.filter(transaction_date__date=date_q)

        return qs.order_by('-transaction_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset().filter(is_cancelled=False)
        totals = qs.aggregate(
            total_rev=Sum('total_amount'),
            total_liters=Sum('quantity'),
            cash_total=Sum('total_amount', filter=Q(payment_method='CASH')),
            credit_total=Sum('total_amount', filter=Q(payment_method='CREDIT')),
            bank_total=Sum('total_amount', filter=Q(payment_method__in=['BANK_TRANSFER', 'QR_FONEPAY'])),
        )
        context['totals'] = totals
        context['fuels'] = FuelType.objects.filter(is_active=True)
        context['q'] = self.request.GET.get('q', '')
        context['selected_fuel'] = self.request.GET.get('fuel', '')
        context['selected_payment'] = self.request.GET.get('payment', '')
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_date'] = self.request.GET.get('date', '')
        return context


@login_required
def manual_sale_create_view(request):
    """Record an authorized manual fuel sales entry."""
    active_shift = Shift.objects.filter(status='OPEN').first()
    if not active_shift:
        messages.error(request, _("No active shift open. Please open a shift before recording sales."))
        return redirect('operations:shift_list')

    if request.method == 'POST':
        form = ManualSaleForm(request.POST)
        if form.is_valid():
            try:
                fuel_type = form.cleaned_data['fuel_type']
                tank = form.cleaned_data['tank']
                nozzle = form.cleaned_data['nozzle']
                quantity = form.cleaned_data['quantity']
                unit_price = form.cleaned_data['unit_price']
                payment_method = form.cleaned_data['payment_method']
                customer_name = form.cleaned_data['customer_name']
                vehicle_number = form.cleaned_data['vehicle_number']
                reason = form.cleaned_data['reason_for_manual']

                sale = record_manual_sale(
                    shift=active_shift,
                    fuel_type=fuel_type,
                    tank=tank,
                    quantity=quantity,
                    unit_price=unit_price,
                    payment_method=payment_method,
                    recorded_by=request.user,
                    reason_for_manual=reason,
                    customer_name=customer_name,
                    vehicle_number=vehicle_number,
                    nozzle=nozzle,
                    authorized_by=request.user,
                )
                messages.success(request, _("Manual sale invoice '%(inv)s' recorded successfully.") % {'inv': sale.invoice_number})
                return redirect('operations:sales_register')
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        # Suggest current price for default fuel
        default_fuel = FuelType.objects.filter(is_active=True).first()
        initial = {}
        if default_fuel:
            eff = default_fuel.get_current_price()
            if eff:
                initial['unit_price'] = eff.selling_price
        form = ManualSaleForm(initial=initial)

    context = {
        'title': _('Record Manual Fuel Sale'),
        'form': form,
        'active_shift': active_shift,
    }
    return render(request, 'operations/manual_sale_form.html', context)


@login_required
def sale_detail_view(request, pk):
    """View invoice details."""
    sale = get_object_or_404(FuelSale.objects.select_related('fuel_type', 'tank', 'nozzle', 'shift', 'recorded_by'), pk=pk)
    return render(request, 'operations/sale_detail.html', {'sale': sale})


@manager_or_owner_required
def sale_cancel_view(request, pk):
    """Void / Cancel a sales transaction and reverse stock into tank."""
    sale = get_object_or_404(FuelSale, pk=pk)
    if sale.is_cancelled:
        messages.warning(request, _("Invoice '%(inv)s' is already voided.") % {'inv': sale.invoice_number})
        return redirect('operations:sale_detail', pk=sale.pk)

    if request.method == 'POST':
        form = SaleCancellationForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['cancellation_reason']
            try:
                cancel_fuel_sale(sale=sale, cancelled_by=request.user, cancellation_reason=reason)
                messages.success(
                    request,
                    _("Invoice '%(inv)s' has been voided and %(qty)s L restored to %(tank)s.") % {
                        'inv': sale.invoice_number,
                        'qty': sale.quantity,
                        'tank': sale.tank.tank_name
                    }
                )
                return redirect('operations:sales_register')
            except Exception as exc:
                messages.error(request, str(exc))
    else:
        form = SaleCancellationForm()

    context = {
        'sale': sale,
        'form': form,
    }
    return render(request, 'operations/sale_cancel.html', context)


# ==============================================================================
# 4. Auditable Stock Movement Ledger
# ==============================================================================

class StockMovementLedgerView(RoleRequiredMixin, ListView):
    model = StockMovement
    template_name = 'operations/stock_ledger.html'
    context_object_name = 'movements'
    paginate_by = 30
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = StockMovement.objects.select_related('tank__fuel_type', 'shift', 'performed_by')
        tank_id = self.request.GET.get('tank', '').strip()
        m_type = self.request.GET.get('type', '').strip()

        if tank_id:
            qs = qs.filter(tank_id=tank_id)
        if m_type:
            qs = qs.filter(movement_type=m_type)

        return qs.order_by('-timestamp', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tanks'] = StorageTank.objects.filter(is_active=True)
        context['movement_types'] = StockMovement.MOVEMENT_TYPE_CHOICES
        context['selected_tank'] = self.request.GET.get('tank', '')
        context['selected_type'] = self.request.GET.get('type', '')
        return context


@manager_or_owner_required
def stock_adjustment_create_view(request):
    """Record dip loss, evaporation, or testing adjustment."""
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            tank = form.cleaned_data['tank']
            m_type = form.cleaned_data['movement_type']
            quantity = form.cleaned_data['quantity']
            remarks = form.cleaned_data['remarks']

            try:
                record_stock_movement(
                    tank=tank,
                    movement_type=m_type,
                    quantity=quantity,
                    performed_by=request.user,
                    reference_type='ManualAdjustment',
                    remarks=remarks or f"Authorized adjustment by {request.user.username}"
                )
                messages.success(request, _("Stock adjustment of %(qty)s L recorded for tank %(tank)s.") % {
                    'qty': quantity,
                    'tank': tank.tank_number
                })
                return redirect('operations:stock_ledger')
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        form = StockAdjustmentForm()

    context = {
        'title': _('Record Tank Stock Adjustment'),
        'form': form,
    }
    return render(request, 'operations/stock_adjustment_form.html', context)


# ==============================================================================
# 5. Sales Reconciliation & Multi-Dimensional Reports
# ==============================================================================

@login_required
def sales_reconciliation_view(request):
    """
    Multi-dimensional sales reconciliation report:
    Nozzle-wise, Pump-wise, Shift-wise, Fuel-wise, and Payment-method-wise breakdowns.
    """
    if not (request.user.is_owner or request.user.is_manager or request.user.is_accountant):
        messages.error(request, _("Permission denied to access sales reconciliation."))
        return redirect('dashboard:index')

    # Date filters
    today = timezone.now().date()
    start_date = request.GET.get('start_date', str(today))
    end_date = request.GET.get('end_date', str(today))

    sales_qs = FuelSale.objects.filter(
        transaction_date__date__range=[start_date, end_date],
        is_cancelled=False
    )

    # 1. Overall Revenue & Volume Totals
    overall = sales_qs.aggregate(
        total_revenue=Sum('total_amount'),
        total_volume=Sum('quantity'),
        total_tx=Count('id'),
    )

    # 2. Fuel-wise breakdown
    fuel_breakdown = sales_qs.values(
        'fuel_type__code', 'fuel_type__name_en', 'fuel_type__color_code'
    ).annotate(
        volume=Sum('quantity'),
        revenue=Sum('total_amount'),
        tx_count=Count('id')
    ).order_by('-revenue')

    # 3. Nozzle-wise breakdown
    nozzle_breakdown = sales_qs.filter(nozzle__isnull=False).values(
        'nozzle__nozzle_code', 'nozzle__pump__pump_name', 'fuel_type__code'
    ).annotate(
        volume=Sum('quantity'),
        revenue=Sum('total_amount'),
        tx_count=Count('id')
    ).order_by('nozzle__nozzle_code')

    # 4. Pump-wise breakdown
    pump_breakdown = sales_qs.filter(nozzle__isnull=False).values(
        'nozzle__pump__pump_number', 'nozzle__pump__pump_name'
    ).annotate(
        volume=Sum('quantity'),
        revenue=Sum('total_amount')
    ).order_by('nozzle__pump__pump_number')

    # 5. Payment Method breakdown
    payment_breakdown = sales_qs.values('payment_method').annotate(
        revenue=Sum('total_amount'),
        tx_count=Count('id')
    ).order_by('-revenue')

    # 6. Sale Type breakdown (Meter vs Manual)
    type_breakdown = sales_qs.values('sale_type').annotate(
        volume=Sum('quantity'),
        revenue=Sum('total_amount'),
        tx_count=Count('id')
    )

    # 7. Shift-wise summary in date range
    shifts_summary = Shift.objects.filter(
        date_ad__range=[start_date, end_date]
    ).select_related('schedule', 'supervisor').annotate(
        total_shift_sales=Sum('sales__total_amount', filter=Q(sales__is_cancelled=False)),
        total_shift_qty=Sum('sales__quantity', filter=Q(sales__is_cancelled=False)),
    ).order_by('-opening_time')

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'overall': overall,
        'fuel_breakdown': fuel_breakdown,
        'nozzle_breakdown': nozzle_breakdown,
        'pump_breakdown': pump_breakdown,
        'payment_breakdown': payment_breakdown,
        'type_breakdown': type_breakdown,
        'shifts_summary': shifts_summary,
    }
    return render(request, 'operations/sales_reconciliation.html', context)
