import csv
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import CategoryForm, TransactionForm
from .models import Category, Transaction

MONTH_OPTIONS = [
    (1, 'Janeiro'),
    (2, 'Fevereiro'),
    (3, 'Marco'),
    (4, 'Abril'),
    (5, 'Maio'),
    (6, 'Junho'),
    (7, 'Julho'),
    (8, 'Agosto'),
    (9, 'Setembro'),
    (10, 'Outubro'),
    (11, 'Novembro'),
    (12, 'Dezembro'),
]


def parse_positive_int(value, default=None, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if minimum is not None and parsed < minimum:
        return default
    if maximum is not None and parsed > maximum:
        return default
    return parsed


def build_last_months(selected_year, selected_month, total=6):
    months = []
    year = selected_year
    month = selected_month

    for _ in range(total):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    months.reverse()
    return months


def apply_transaction_filters(queryset, params, fallback_to_current=False):
    today = date.today()
    default_month = today.month if fallback_to_current else None
    default_year = today.year if fallback_to_current else None

    month = parse_positive_int(params.get('month'), default=default_month, minimum=1, maximum=12)
    year = parse_positive_int(params.get('year'), default=default_year, minimum=2000, maximum=2100)
    category_id = parse_positive_int(params.get('category'), default=None, minimum=1)
    query = params.get('q', '').strip()

    if month:
        queryset = queryset.filter(date__month=month)
    if year:
        queryset = queryset.filter(date__year=year)
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    if query:
        queryset = queryset.filter(Q(description__icontains=query) | Q(notes__icontains=query))

    return queryset, {
        'month': month or '',
        'year': year or '',
        'category': category_id or '',
        'q': query,
    }


class UserOwnedQuerysetMixin(LoginRequiredMixin):
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'finances/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_transactions = Transaction.objects.filter(user=self.request.user)
        current_transactions, filters = apply_transaction_filters(
            user_transactions,
            self.request.GET,
            fallback_to_current=True,
        )

        selected_month = filters['month']
        selected_year = filters['year']

        total_income = current_transactions.filter(type=Transaction.Type.INCOME).aggregate(total=Sum('amount'))['total']
        total_expense = current_transactions.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total']

        total_income = total_income or Decimal('0')
        total_expense = total_expense or Decimal('0')
        balance = total_income - total_expense

        expenses_by_category = (
            current_transactions.filter(type=Transaction.Type.EXPENSE)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        expense_labels = [item['category__name'] for item in expenses_by_category]
        expense_values = [float(item['total']) for item in expenses_by_category]

        month_series = build_last_months(selected_year, selected_month, total=6)
        evolution_labels = []
        evolution_income = []
        evolution_expense = []

        for year, month in month_series:
            month_transactions = user_transactions.filter(date__year=year, date__month=month)
            month_income = month_transactions.filter(type=Transaction.Type.INCOME).aggregate(total=Sum('amount'))['total']
            month_expense = month_transactions.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total']
            evolution_labels.append(f'{month:02d}/{year}')
            evolution_income.append(float(month_income or Decimal('0')))
            evolution_expense.append(float(month_expense or Decimal('0')))

        context.update(
            {
                'month_options': MONTH_OPTIONS,
                'selected_month': selected_month,
                'selected_year': selected_year,
                'total_income': total_income,
                'total_expense': total_expense,
                'balance': balance,
                'recent_transactions': current_transactions.select_related('category')[:10],
                'expense_labels': expense_labels,
                'expense_values': expense_values,
                'evolution_labels': evolution_labels,
                'evolution_income': evolution_income,
                'evolution_expense': evolution_expense,
            }
        )
        return context


class CategoryListView(UserOwnedQuerysetMixin, ListView):
    template_name = 'finances/category_list.html'
    model = Category
    context_object_name = 'categories'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q', '').strip()
        category_type = self.request.GET.get('type', '').strip()

        if query:
            queryset = queryset.filter(name__icontains=query)
        if category_type in {Category.Type.INCOME, Category.Type.EXPENSE}:
            queryset = queryset.filter(type=category_type)

        self.active_filters = {'q': query, 'type': category_type}
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_without_page'] = params.urlencode()
        context['filters'] = getattr(self, 'active_filters', {'q': '', 'type': ''})
        context['type_choices'] = Category.Type.choices
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    template_name = 'finances/category_form.html'
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy('finances:category_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Categoria criada com sucesso.')
        return super().form_valid(form)


class CategoryUpdateView(UserOwnedQuerysetMixin, UpdateView):
    template_name = 'finances/category_form.html'
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy('finances:category_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Categoria atualizada com sucesso.')
        return super().form_valid(form)


class CategoryDeleteView(UserOwnedQuerysetMixin, DeleteView):
    template_name = 'finances/category_confirm_delete.html'
    model = Category
    success_url = reverse_lazy('finances:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Categoria removida com sucesso.')
        return super().form_valid(form)


class TransactionListView(UserOwnedQuerysetMixin, ListView):
    template_name = 'finances/transaction_list.html'
    model = Transaction
    context_object_name = 'transactions'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('category')
        queryset, self.active_filters = apply_transaction_filters(queryset, self.request.GET)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_without_page'] = params.urlencode()
        context['filters'] = getattr(self, 'active_filters', {'month': '', 'year': '', 'category': '', 'q': ''})
        context['month_options'] = MONTH_OPTIONS
        context['categories'] = Category.objects.filter(user=self.request.user).order_by('name')
        return context


class TransactionCreateView(LoginRequiredMixin, CreateView):
    template_name = 'finances/transaction_form.html'
    model = Transaction
    form_class = TransactionForm
    success_url = reverse_lazy('finances:transaction_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['date'] = date.today()
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Lancamento criado com sucesso.')
        return super().form_valid(form)


class TransactionUpdateView(UserOwnedQuerysetMixin, UpdateView):
    template_name = 'finances/transaction_form.html'
    model = Transaction
    form_class = TransactionForm
    success_url = reverse_lazy('finances:transaction_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Lancamento atualizado com sucesso.')
        return super().form_valid(form)


class TransactionDeleteView(UserOwnedQuerysetMixin, DeleteView):
    template_name = 'finances/transaction_confirm_delete.html'
    model = Transaction
    success_url = reverse_lazy('finances:transaction_list')

    def form_valid(self, form):
        messages.success(self.request, 'Lancamento removido com sucesso.')
        return super().form_valid(form)


class MonthlySummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'finances/monthly_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        selected_month = parse_positive_int(self.request.GET.get('month'), default=today.month, minimum=1, maximum=12)
        selected_year = parse_positive_int(self.request.GET.get('year'), default=today.year, minimum=2000, maximum=2100)

        month_transactions = Transaction.objects.filter(
            user=self.request.user,
            date__month=selected_month,
            date__year=selected_year,
        )

        total_income = month_transactions.filter(type=Transaction.Type.INCOME).aggregate(total=Sum('amount'))['total']
        total_expense = month_transactions.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total']

        total_income = total_income or Decimal('0')
        total_expense = total_expense or Decimal('0')
        balance = total_income - total_expense

        income_totals = (
            month_transactions.filter(type=Transaction.Type.INCOME)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        expense_totals = (
            month_transactions.filter(type=Transaction.Type.EXPENSE)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        expense_percentages = []
        for item in expense_totals:
            percentage = (item['total'] / total_expense * 100) if total_expense else Decimal('0')
            expense_percentages.append(
                {
                    'category_name': item['category__name'],
                    'total': item['total'],
                    'percentage': float(round(percentage, 2)),
                }
            )

        context.update(
            {
                'month_options': MONTH_OPTIONS,
                'selected_month': selected_month,
                'selected_year': selected_year,
                'total_income': total_income,
                'total_expense': total_expense,
                'balance': balance,
                'income_totals': income_totals,
                'expense_totals': expense_totals,
                'expense_percentages': expense_percentages,
            }
        )
        return context


@login_required
def export_transactions_csv(request):
    queryset = Transaction.objects.filter(user=request.user).select_related('category')
    filtered_queryset, _ = apply_transaction_filters(queryset, request.GET)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="lancamentos.csv"'

    writer = csv.writer(response)
    writer.writerow(['Data', 'Tipo', 'Categoria', 'Valor', 'Descricao', 'Observacao', 'Recorrente'])

    for transaction in filtered_queryset.order_by('-date', '-id'):
        writer.writerow(
            [
                transaction.date.isoformat(),
                transaction.get_type_display(),
                transaction.category.name,
                transaction.amount,
                transaction.description,
                transaction.notes,
                'Sim' if transaction.is_recurring else 'Nao',
            ]
        )

    return response
