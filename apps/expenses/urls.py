from django.urls import path
from apps.expenses import views

app_name = 'expenses'

urlpatterns = [
    path('', views.ExpenseListView.as_view(), name='expense_list'),
    path('new/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('<int:pk>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
]
