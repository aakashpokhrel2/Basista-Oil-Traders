from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from apps.expenses.models import ExpenseCategory, Expense
from apps.expenses.forms import ExpenseForm, ExpenseCategoryForm
from apps.expenses.services import record_and_approve_expense
from common.permissions import RoleRequiredMixin
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT


class ExpenseListView(RoleRequiredMixin, ListView):
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 25
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = Expense.objects.select_related('category', 'recorded_by')
        cat_id = self.request.GET.get('category')
        method = self.request.GET.get('method')
        date_q = self.request.GET.get('date')

        if cat_id:
            qs = qs.filter(category_id=cat_id)
        if method:
            qs = qs.filter(payment_method=method)
        if date_q:
            qs = qs.filter(date=date_q)

        return qs.order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = ExpenseCategory.objects.filter(is_active=True)
        ctx['total_expenses'] = self.get_queryset().aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
        ctx['selected_category'] = self.request.GET.get('category', '')
        ctx['selected_method'] = self.request.GET.get('method', '')
        return ctx


class ExpenseCreateView(RoleRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expenses/expense_form.html'
    success_url = reverse_lazy('expenses:expense_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def form_valid(self, form):
        try:
            exp = record_and_approve_expense(
                category=form.cleaned_data['category'],
                amount=form.cleaned_data['amount'],
                description=form.cleaned_data['description'],
                payment_method=form.cleaned_data['payment_method'],
                payee_name=form.cleaned_data['payee_name'],
                reference_number=form.cleaned_data['reference_number'],
                supporting_document=form.cleaned_data.get('supporting_document'),
                recorded_by=self.request.user,
                expense_date=form.cleaned_data['date']
            )
            messages.success(self.request, _("Expense voucher '%(v)s' recorded successfully.") % {'v': exp.voucher_number})
            return redirect(self.success_url)
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)


class ExpenseDetailView(RoleRequiredMixin, DetailView):
    model = Expense
    template_name = 'expenses/expense_detail.html'
    context_object_name = 'expense'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]
