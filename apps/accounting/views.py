from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from apps.accounting.models import Account, JournalEntry, CashTransaction
from apps.accounting.forms import CashTransferForm
from apps.accounting.services import record_cash_transaction, create_journal_entry
from common.permissions import RoleRequiredMixin, role_required
from common.roles import ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT


class ChartOfAccountsView(RoleRequiredMixin, ListView):
    model = Account
    template_name = 'accounting/account_list.html'
    context_object_name = 'accounts'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        return Account.objects.filter(is_active=True).order_by('account_number')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        accounts = list(ctx['accounts'])
        ctx['grouped_accounts'] = {
            'ASSET': [a for a in accounts if a.account_type == 'ASSET'],
            'LIABILITY': [a for a in accounts if a.account_type == 'LIABILITY'],
            'EQUITY': [a for a in accounts if a.account_type == 'EQUITY'],
            'REVENUE': [a for a in accounts if a.account_type == 'REVENUE'],
            'EXPENSE': [a for a in accounts if a.account_type == 'EXPENSE'],
        }
        return ctx


class JournalEntryListView(RoleRequiredMixin, ListView):
    model = JournalEntry
    template_name = 'accounting/journal_list.html'
    context_object_name = 'entries'
    paginate_by = 25
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = JournalEntry.objects.prefetch_related('lines__account').select_related('created_by')
        date_q = self.request.GET.get('date')
        if date_q:
            qs = qs.filter(date=date_q)
        return qs.order_by('-date', '-created_at')


class JournalEntryDetailView(RoleRequiredMixin, DetailView):
    model = JournalEntry
    template_name = 'accounting/journal_detail.html'
    context_object_name = 'entry'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]


class CashBookView(RoleRequiredMixin, ListView):
    model = CashTransaction
    template_name = 'accounting/cash_book.html'
    context_object_name = 'transactions'
    paginate_by = 30
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = CashTransaction.objects.select_related('performed_by')
        date_q = self.request.GET.get('date')
        t_type = self.request.GET.get('type')
        if date_q:
            qs = qs.filter(date=date_q)
        if t_type:
            qs = qs.filter(transaction_type=t_type)
        return qs.order_by('-date', '-created_at', '-id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        latest_tx = CashTransaction.objects.order_by('-date', '-created_at', '-id').first()
        ctx['current_cash_balance'] = latest_tx.balance_after if latest_tx else Decimal('0.00')
        inflows = self.get_queryset().filter(transaction_type='INFLOW').aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
        outflows = self.get_queryset().filter(transaction_type='OUTFLOW').aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
        ctx['total_inflows'] = inflows
        ctx['total_outflows'] = outflows
        return ctx


@role_required([ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT])
def cash_transfer_view(request):
    """Deposit cash into bank or withdraw from bank for float."""
    if request.method == 'POST':
        form = CashTransferForm(request.POST)
        if form.is_valid():
            t_type = form.cleaned_data['transfer_type']
            amount = form.cleaned_data['amount']
            ref = form.cleaned_data['bank_reference']
            desc = form.cleaned_data['description']

            try:
                cash_acct = Account.objects.get(account_number='1010')
                bank_acct = Account.objects.get(account_number='1020')

                if t_type == 'BANK_DEPOSIT':
                    # Cash -> Bank: Drawer outflow, Bank debit
                    record_cash_transaction(
                        transaction_type='OUTFLOW',
                        source_category='BANK_DEPOSIT',
                        amount=amount,
                        performed_by=request.user,
                        description=f"Bank Deposit ({ref}): {desc}",
                        reference_type='BankDeposit',
                        reference_id=ref
                    )
                    create_journal_entry(
                        date=None,
                        description=f"Bank Deposit: {desc} (Slip #{ref})",
                        lines_data=[
                            {'account': bank_acct, 'debit': amount, 'credit': Decimal('0.00'), 'description': 'Deposit into bank'},
                            {'account': cash_acct, 'debit': Decimal('0.00'), 'credit': amount, 'description': 'Cash removed from drawer'},
                        ],
                        created_by=request.user,
                        reference_type='BankDeposit',
                        reference_id=ref
                    )
                    messages.success(request, _("Bank deposit of NPR %(amt)s recorded.") % {'amt': amount})
                else:  # BANK_WITHDRAWAL
                    # Bank -> Cash: Drawer inflow, Bank credit
                    record_cash_transaction(
                        transaction_type='INFLOW',
                        source_category='BANK_WITHDRAWAL',
                        amount=amount,
                        performed_by=request.user,
                        description=f"Bank Withdrawal ({ref}): {desc}",
                        reference_type='BankWithdrawal',
                        reference_id=ref
                    )
                    create_journal_entry(
                        date=None,
                        description=f"Bank Withdrawal for Float: {desc} (Cheque #{ref})",
                        lines_data=[
                            {'account': cash_acct, 'debit': amount, 'credit': Decimal('0.00'), 'description': 'Cash float to drawer'},
                            {'account': bank_acct, 'debit': Decimal('0.00'), 'credit': amount, 'description': 'Withdrawn from bank'},
                        ],
                        created_by=request.user,
                        reference_type='BankWithdrawal',
                        reference_id=ref
                    )
                    messages.success(request, _("Bank withdrawal of NPR %(amt)s recorded into drawer.") % {'amt': amount})

                return redirect('accounting:cash_book')
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        form = CashTransferForm()

    return render(request, 'accounting/cash_transfer_form.html', {
        'form': form,
        'title': _('Bank Cash Deposit / Withdrawal')
    })
