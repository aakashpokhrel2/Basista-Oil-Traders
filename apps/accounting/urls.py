from django.urls import path
from apps.accounting import views

app_name = 'accounting'

urlpatterns = [
    # Chart of Accounts
    path('coa/', views.ChartOfAccountsView.as_view(), name='account_list'),

    # General Journal
    path('journal/', views.JournalEntryListView.as_view(), name='journal_list'),
    path('journal/<int:pk>/', views.JournalEntryDetailView.as_view(), name='journal_detail'),

    # Cash Book
    path('cash-book/', views.CashBookView.as_view(), name='cash_book'),
    path('cash-book/transfer/', views.cash_transfer_view, name='cash_transfer'),
]
