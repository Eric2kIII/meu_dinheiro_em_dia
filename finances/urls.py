from django.urls import path

from .views import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    DashboardView,
    MonthlySummaryView,
    TransactionCreateView,
    TransactionDeleteView,
    TransactionListView,
    TransactionUpdateView,
    export_transactions_csv,
)

app_name = 'finances'

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('categorias/', CategoryListView.as_view(), name='category_list'),
    path('categorias/nova/', CategoryCreateView.as_view(), name='category_create'),
    path('categorias/<int:pk>/editar/', CategoryUpdateView.as_view(), name='category_update'),
    path('categorias/<int:pk>/excluir/', CategoryDeleteView.as_view(), name='category_delete'),
    path('lancamentos/', TransactionListView.as_view(), name='transaction_list'),
    path('lancamentos/novo/', TransactionCreateView.as_view(), name='transaction_create'),
    path('lancamentos/<int:pk>/editar/', TransactionUpdateView.as_view(), name='transaction_update'),
    path('lancamentos/<int:pk>/excluir/', TransactionDeleteView.as_view(), name='transaction_delete'),
    path('lancamentos/exportar-csv/', export_transactions_csv, name='transaction_export_csv'),
    path('resumo-mensal/', MonthlySummaryView.as_view(), name='monthly_summary'),
]
