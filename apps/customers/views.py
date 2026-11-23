from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Q

from apps.customers.models import Customer, CustomerPayment
from apps.customers.forms import CustomerForm, CustomerPaymentForm
from apps.customers.services import record_customer_payment
from common.permissions import RoleRequiredMixin, role_required
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER


class CustomerListView(RoleRequiredMixin, ListView):
    model = Customer
    template_name = 'customers/customer_list.html'
    context_object_name = 'customers'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER]

    def get_queryset(self):
        qs = Customer.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(pan_vat_number__icontains=q))
        return qs.order_by('-current_balance', 'name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_credit'] = Customer.objects.aggregate(tot=Sum('current_balance'))['tot'] or Decimal('0.00')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class CustomerCreateView(RoleRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    success_url = reverse_lazy('customers:customer_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def form_valid(self, form):
        customer = form.save()
        messages.success(self.request, _("Customer '%(name)s' registered.") % {'name': customer.name})
        return redirect(self.success_url)


class CustomerDetailView(RoleRequiredMixin, DetailView):
    model = Customer
    template_name = 'customers/customer_detail.html'
    context_object_name = 'customer'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payments'] = self.object.payments.all().order_by('-payment_date')[:30]
        # Credit fuel sales to this customer (by matching customer_name)
        from apps.operations.models import FuelSale
        ctx['credit_sales'] = FuelSale.objects.filter(
            customer_name__icontains=self.object.name,
            payment_method='CREDIT',
            is_cancelled=False
        ).order_by('-transaction_date')[:30]
        return ctx


@role_required([ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_CASHIER])
def customer_payment_create_view(request, customer_id):
    """Record credit repayment from customer."""
    customer = get_object_or_404(Customer, pk=customer_id)
    if request.method == 'POST':
        form = CustomerPaymentForm(request.POST)
        if form.is_valid():
            try:
                record_customer_payment(
                    customer=customer,
                    amount=form.cleaned_data['amount'],
                    payment_method=form.cleaned_data['payment_method'],
                    reference_number=form.cleaned_data['reference_number'],
                    payment_date=form.cleaned_data['payment_date'],
                    notes=form.cleaned_data['notes'],
                    recorded_by=request.user
                )
                messages.success(request, _("Collection of NPR %(amt)s recorded from %(c)s.") % {
                    'amt': form.cleaned_data['amount'],
                    'c': customer.name
                })
                return redirect('customers:customer_detail', pk=customer.pk)
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        form = CustomerPaymentForm()

    return render(request, 'customers/payment_form.html', {
        'customer': customer,
        'form': form,
        'title': _('Record Customer Credit Collection')
    })
