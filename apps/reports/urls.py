from django.urls import path
from apps.reports import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_hub_view, name='hub'),
    path('sales/', views.sales_report_view, name='sales_report'),
    path('inventory/', views.inventory_report_view, name='inventory_report'),
    path('financial/', views.financial_statements_view, name='financial_statements'),

    # Exports
    path('export/sales/excel/', views.export_sales_excel_view, name='export_sales_excel'),
    path('export/pnl/pdf/', views.export_pnl_pdf_view, name='export_pnl_pdf'),
]
