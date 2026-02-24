import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    CategoryForm,
    CreditCardExpenseForm,
    CreditCardForm,
    CreditCardPaymentForm,
    ImportFileForm,
    TransactionForm,
)
from .importers import import_categories_from_file, import_transactions_from_file
from .models import Category, CreditCard, CreditCardExpense, CreditCardPayment, Transaction

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


def combine_category_totals(*querysets):
    combined = defaultdict(lambda: Decimal('0'))
    for queryset in querysets:
        for item in queryset:
            name = item.get('category__name') or 'Sem categoria'
            combined[name] += item.get('total') or Decimal('0')

    totals = [{'category_name': name, 'total': total} for name, total in combined.items()]
    totals.sort(key=lambda item: item['total'], reverse=True)
    return totals


def build_credit_card_summary(user, selected_month, selected_year):
    cards = CreditCard.objects.filter(user=user).order_by('name')

    month_expenses = CreditCardExpense.objects.filter(
        user=user,
        date__month=selected_month,
        date__year=selected_year,
    )
    month_payments = CreditCardPayment.objects.filter(
        user=user,
        date__month=selected_month,
        date__year=selected_year,
    )

    expense_totals = {
        item['card_id']: item['total'] or Decimal('0')
        for item in month_expenses.values('card_id').annotate(total=Sum('amount'))
    }
    payment_totals = {
        item['card_id']: item['total'] or Decimal('0')
        for item in month_payments.values('card_id').annotate(total=Sum('amount'))
    }

    card_summaries = []
    for card in cards:
        expense_total = expense_totals.get(card.id, Decimal('0'))
        payment_total = payment_totals.get(card.id, Decimal('0'))
        card_summaries.append(
            {
                'card': card,
                'expense_total': expense_total,
                'payment_total': payment_total,
                'open_balance': expense_total - payment_total,
            }
        )

    total_expense = sum((item['expense_total'] for item in card_summaries), Decimal('0'))
    total_payment = sum((item['payment_total'] for item in card_summaries), Decimal('0'))

    return {
        'card_summaries': card_summaries,
        'total_expense': total_expense,
        'total_payment': total_payment,
        'expenses_queryset': month_expenses,
        'payments_queryset': month_payments,
    }


def add_import_messages(request, report, entity_label):
    messages.success(
        request,
        f'Importacao de {entity_label} concluida: {report.get("created", 0)} itens criados.',
    )

    skipped = report.get('skipped', 0)
    if skipped:
        messages.info(request, f'{skipped} itens ignorados por ja existirem.')

    errors = report.get('errors', [])
    if errors:
        preview = errors[:5]
        for error_message in preview:
            messages.error(request, error_message)
        if len(errors) > len(preview):
            messages.warning(request, f'Foram encontrados mais {len(errors) - len(preview)} erros.')


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
        transaction_expense_total = current_transactions.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total']

        total_income = total_income or Decimal('0')
        transaction_expense_total = transaction_expense_total or Decimal('0')

        card_context = build_credit_card_summary(self.request.user, selected_month, selected_year)
        card_expense_total = card_context['total_expense']

        total_expense = transaction_expense_total + card_expense_total
        balance = total_income - total_expense

        transaction_expenses_by_category = (
            current_transactions.filter(type=Transaction.Type.EXPENSE)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        card_expenses_by_category = (
            card_context['expenses_queryset']
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        combined_expenses_by_category = combine_category_totals(
            transaction_expenses_by_category,
            card_expenses_by_category,
        )
        expense_labels = [item['category_name'] for item in combined_expenses_by_category]
        expense_values = [float(item['total']) for item in combined_expenses_by_category]

        month_series = build_last_months(selected_year, selected_month, total=6)
        evolution_labels = []
        evolution_income = []
        evolution_expense = []

        for year, month in month_series:
            month_transactions = user_transactions.filter(date__year=year, date__month=month)
            month_income = month_transactions.filter(type=Transaction.Type.INCOME).aggregate(total=Sum('amount'))['total']
            month_expense = month_transactions.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total']
            month_card_expense = CreditCardExpense.objects.filter(
                user=self.request.user,
                date__year=year,
                date__month=month,
            ).aggregate(total=Sum('amount'))['total']

            evolution_labels.append(f'{month:02d}/{year}')
            evolution_income.append(float(month_income or Decimal('0')))
            evolution_expense.append(float((month_expense or Decimal('0')) + (month_card_expense or Decimal('0'))))

        context.update(
            {
                'month_options': MONTH_OPTIONS,
                'selected_month': selected_month,
                'selected_year': selected_year,
                'total_income': total_income,
                'total_expense': total_expense,
                'balance': balance,
                'transaction_expense_total': transaction_expense_total,
                'credit_card_expense_total': card_expense_total,
                'credit_card_payment_total': card_context['total_payment'],
                'recent_transactions': current_transactions.select_related('category')[:10],
                'expense_labels': expense_labels,
                'expense_values': expense_values,
                'evolution_labels': evolution_labels,
                'evolution_income': evolution_income,
                'evolution_expense': evolution_expense,
                'card_summaries': card_context['card_summaries'],
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

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return str(self.success_url)


class CategoryImportView(LoginRequiredMixin, FormView):
    template_name = 'finances/category_import.html'
    form_class = ImportFileForm
    success_url = reverse_lazy('finances:category_list')

    def form_valid(self, form):
        report = import_categories_from_file(form.cleaned_data['file'], self.request.user)
        add_import_messages(self.request, report, 'categorias')
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


@login_required
def download_category_import_template(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="modelo_categorias.csv"'

    writer = csv.writer(response)
    writer.writerow(['name', 'type'])
    writer.writerow(['Salario', 'INCOME'])
    writer.writerow(['Alimentacao', 'EXPENSE'])
    return response


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
        initial['type'] = Transaction.Type.INCOME
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = Category.objects.filter(user=self.request.user).order_by('name')
        context['category_options'] = [
            {
                'id': category.id,
                'name': category.name,
                'type': category.type,
                'type_label': category.get_type_display(),
            }
            for category in categories
        ]
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Lancamento criado com sucesso.')
        return super().form_valid(form)


class TransactionImportView(LoginRequiredMixin, FormView):
    template_name = 'finances/transaction_import.html'
    form_class = ImportFileForm
    success_url = reverse_lazy('finances:transaction_list')

    def form_valid(self, form):
        report = import_transactions_from_file(form.cleaned_data['file'], self.request.user)
        add_import_messages(self.request, report, 'lancamentos')
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = Category.objects.filter(user=self.request.user).order_by('name')
        context['category_options'] = [
            {
                'id': category.id,
                'name': category.name,
                'type': category.type,
                'type_label': category.get_type_display(),
            }
            for category in categories
        ]
        return context

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


@login_required
def download_transaction_import_template(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="modelo_lancamentos.csv"'

    writer = csv.writer(response)
    writer.writerow(['type', 'amount', 'date', 'category', 'description', 'notes', 'is_recurring'])
    writer.writerow(['INCOME', '5200.00', '2026-02-05', 'Salario', 'Recebimento mensal', '', 'false'])
    writer.writerow(['EXPENSE', '89.90', '2026-02-07', 'Alimentacao', 'Mercado', 'Compra semanal', 'false'])
    return response


class CreditCardOverviewView(LoginRequiredMixin, TemplateView):
    template_name = 'finances/credit_card_overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        selected_month = parse_positive_int(self.request.GET.get('month'), default=today.month, minimum=1, maximum=12)
        selected_year = parse_positive_int(self.request.GET.get('year'), default=today.year, minimum=2000, maximum=2100)

        card_context = build_credit_card_summary(self.request.user, selected_month, selected_year)

        context.update(
            {
                'month_options': MONTH_OPTIONS,
                'selected_month': selected_month,
                'selected_year': selected_year,
                'card_summaries': card_context['card_summaries'],
                'credit_card_expense_total': card_context['total_expense'],
                'credit_card_payment_total': card_context['total_payment'],
                'recent_card_expenses': card_context['expenses_queryset'].select_related('card', 'category')[:10],
                'recent_card_payments': card_context['payments_queryset'].select_related('card')[:10],
            }
        )
        return context


class CreditCardCreateView(LoginRequiredMixin, CreateView):
    template_name = 'finances/credit_card_form.html'
    model = CreditCard
    form_class = CreditCardForm
    success_url = reverse_lazy('finances:credit_card_overview')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Cartao cadastrado com sucesso.')
        return super().form_valid(form)


class CreditCardUpdateView(UserOwnedQuerysetMixin, UpdateView):
    template_name = 'finances/credit_card_form.html'
    model = CreditCard
    form_class = CreditCardForm
    success_url = reverse_lazy('finances:credit_card_overview')

    def form_valid(self, form):
        messages.success(self.request, 'Cartao atualizado com sucesso.')
        return super().form_valid(form)


class CreditCardDeleteView(UserOwnedQuerysetMixin, DeleteView):
    template_name = 'finances/credit_card_confirm_delete.html'
    model = CreditCard
    success_url = reverse_lazy('finances:credit_card_overview')

    def form_valid(self, form):
        messages.success(self.request, 'Cartao removido com sucesso.')
        return super().form_valid(form)


class CreditCardExpenseCreateView(LoginRequiredMixin, CreateView):
    template_name = 'finances/credit_card_expense_form.html'
    model = CreditCardExpense
    form_class = CreditCardExpenseForm
    success_url = reverse_lazy('finances:credit_card_overview')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Despesa de cartao registrada com sucesso.')
        return super().form_valid(form)


class CreditCardExpenseUpdateView(UserOwnedQuerysetMixin, UpdateView):
    template_name = 'finances/credit_card_expense_form.html'
    model = CreditCardExpense
    form_class = CreditCardExpenseForm
    success_url = reverse_lazy('finances:credit_card_overview')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Despesa de cartao atualizada com sucesso.')
        return super().form_valid(form)


class CreditCardExpenseDeleteView(UserOwnedQuerysetMixin, DeleteView):
    template_name = 'finances/credit_card_expense_confirm_delete.html'
    model = CreditCardExpense
    success_url = reverse_lazy('finances:credit_card_overview')

    def form_valid(self, form):
        messages.success(self.request, 'Despesa de cartao removida com sucesso.')
        return super().form_valid(form)


class CreditCardPaymentCreateView(LoginRequiredMixin, CreateView):
    template_name = 'finances/credit_card_payment_form.html'
    model = CreditCardPayment
    form_class = CreditCardPaymentForm
    success_url = reverse_lazy('finances:credit_card_overview')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Pagamento de cartao registrado com sucesso.')
        return super().form_valid(form)


class CreditCardPaymentUpdateView(UserOwnedQuerysetMixin, UpdateView):
    template_name = 'finances/credit_card_payment_form.html'
    model = CreditCardPayment
    form_class = CreditCardPaymentForm
    success_url = reverse_lazy('finances:credit_card_overview')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Pagamento de cartao atualizado com sucesso.')
        return super().form_valid(form)


class CreditCardPaymentDeleteView(UserOwnedQuerysetMixin, DeleteView):
    template_name = 'finances/credit_card_payment_confirm_delete.html'
    model = CreditCardPayment
    success_url = reverse_lazy('finances:credit_card_overview')

    def form_valid(self, form):
        messages.success(self.request, 'Pagamento de cartao removido com sucesso.')
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
        transaction_expense_total = month_transactions.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total']

        total_income = total_income or Decimal('0')
        transaction_expense_total = transaction_expense_total or Decimal('0')

        card_context = build_credit_card_summary(self.request.user, selected_month, selected_year)

        total_expense = transaction_expense_total + card_context['total_expense']
        balance = total_income - total_expense

        income_totals = (
            month_transactions.filter(type=Transaction.Type.INCOME)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        transaction_expense_totals = (
            month_transactions.filter(type=Transaction.Type.EXPENSE)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        card_expense_totals = (
            card_context['expenses_queryset']
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        merged_expense_totals = combine_category_totals(transaction_expense_totals, card_expense_totals)

        expense_percentages = []
        for item in merged_expense_totals:
            percentage = (item['total'] / total_expense * 100) if total_expense else Decimal('0')
            expense_percentages.append(
                {
                    'category_name': item['category_name'],
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
                'transaction_expense_total': transaction_expense_total,
                'credit_card_expense_total': card_context['total_expense'],
                'credit_card_payment_total': card_context['total_payment'],
                'income_totals': income_totals,
                'expense_percentages': expense_percentages,
                'card_summaries': card_context['card_summaries'],
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
