from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Q

from apps.purchases.models import Supplier, FuelPurchase, SupplierPayment
from apps.purchases.forms import SupplierForm, FuelPurchaseForm, SupplierPaymentForm
from apps.purchases.services import approve_fuel_purchase, record_supplier_payment
from common.permissions import RoleRequiredMixin, manager_or_owner_required, role_required
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT


class SupplierListView(RoleRequiredMixin, ListView):
    model = Supplier
    template_name = 'purchases/supplier_list.html'
    context_object_name = 'suppliers'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = Supplier.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(pan_vat_number__icontains=q))
        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_payable'] = Supplier.objects.aggregate(tot=Sum('current_balance'))['tot'] or Decimal('0.00')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class SupplierCreateView(RoleRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'purchases/supplier_form.html'
    success_url = reverse_lazy('purchases:supplier_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        supplier = form.save(commit=False)
        supplier.current_balance = supplier.opening_payable_balance
        supplier.save()
        messages.success(self.request, _("Supplier '%(name)s' added.") % {'name': supplier.name})
        return redirect(self.success_url)


class SupplierDetailView(RoleRequiredMixin, DetailView):
    model = Supplier
    template_name = 'purchases/supplier_detail.html'
    context_object_name = 'supplier'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['purchases'] = self.object.purchases.all().order_by('-purchase_date')[:20]
        ctx['payments'] = self.object.payments.all().order_by('-payment_date')[:20]
        return ctx


class FuelPurchaseListView(RoleRequiredMixin, ListView):
    model = FuelPurchase
    template_name = 'purchases/purchase_list.html'
    context_object_name = 'purchases'
    paginate_by = 20
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = FuelPurchase.objects.select_related('supplier', 'fuel_type', 'receiving_tank')
        supplier_id = self.request.GET.get('supplier')
        status = self.request.GET.get('status')
        date_q = self.request.GET.get('date')

        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if status:
            qs = qs.filter(approval_status=status)
        if date_q:
            qs = qs.filter(purchase_date=date_q)

        return qs.order_by('-purchase_date', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['suppliers'] = Supplier.objects.filter(status='ACTIVE')
        totals = self.get_queryset().filter(approval_status='APPROVED').aggregate(
            tot_amount=Sum('total_amount'),
            tot_volume=Sum('delivered_quantity'),
            tot_paid=Sum('paid_amount')
        )
        ctx['totals'] = totals
        ctx['selected_supplier'] = self.request.GET.get('supplier', '')
        ctx['selected_status'] = self.request.GET.get('status', '')
        return ctx


class FuelPurchaseCreateView(RoleRequiredMixin, CreateView):
    model = FuelPurchase
    form_class = FuelPurchaseForm
    template_name = 'purchases/purchase_form.html'
    success_url = reverse_lazy('purchases:purchase_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        purchase = form.save(commit=False)
        purchase.created_by = self.request.user
        purchase.save()
        messages.success(self.request, _("Fuel delivery entry for invoice '%(inv)s' recorded (Pending Approval).") % {'inv': purchase.invoice_number})
        return redirect(self.success_url)


class FuelPurchaseDetailView(RoleRequiredMixin, DetailView):
    model = FuelPurchase
    template_name = 'purchases/purchase_detail.html'
    context_object_name = 'purchase'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]


@manager_or_owner_required
def purchase_approve_view(request, pk):
    """Approve tanker delivery, add stock to tank, and post journal entry."""
    purchase = get_object_or_404(FuelPurchase, pk=pk)
    if request.method == 'POST':
        try:
            approve_fuel_purchase(purchase=purchase, approved_by=request.user)
            messages.success(
                request,
                _("Purchase invoice '%(inv)s' approved! %(qty)s L received into %(tank)s.") % {
                    'inv': purchase.invoice_number,
                    'qty': purchase.delivered_quantity,
                    'tank': purchase.receiving_tank.tank_name
                }
            )
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect('purchases:purchase_detail', pk=purchase.pk)


@role_required([ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT])
def supplier_payment_create_view(request, supplier_id):
    """Record payment to supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            try:
                record_supplier_payment(
                    supplier=supplier,
                    amount=form.cleaned_data['amount'],
                    payment_method=form.cleaned_data['payment_method'],
                    payment_reference=form.cleaned_data['payment_reference'],
                    payment_date=form.cleaned_data['payment_date'],
                    notes=form.cleaned_data['notes'],
                    recorded_by=request.user
                )
                messages.success(request, _("Payment of NPR %(amt)s recorded for %(sup)s.") % {
                    'amt': form.cleaned_data['amount'],
                    'sup': supplier.name
                })
                return redirect('purchases:supplier_detail', pk=supplier.pk)
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        form = SupplierPaymentForm()

    return render(request, 'purchases/payment_form.html', {
        'supplier': supplier,
        'form': form,
        'title': _('Record Supplier Payment')
    })
