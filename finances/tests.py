from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import TransactionForm
from .importers import import_categories_from_file, import_transactions_from_file
from .models import Category, CreditCard, CreditCardExpense, Transaction


class TransactionValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='alice', password='password123')
        self.income_category = Category.objects.create(user=self.user, name='Salario', type=Category.Type.INCOME)
        self.expense_category = Category.objects.create(user=self.user, name='Moradia', type=Category.Type.EXPENSE)

    def test_amount_must_be_positive(self):
        transaction = Transaction(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            category=self.expense_category,
            amount=Decimal('0.00'),
            date=date.today(),
        )
        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_category_type_must_match_transaction_type(self):
        transaction = Transaction(
            user=self.user,
            type=Transaction.Type.INCOME,
            category=self.expense_category,
            amount=Decimal('10.00'),
            date=date.today(),
        )
        with self.assertRaises(ValidationError):
            transaction.full_clean()


class OwnershipTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user_one = user_model.objects.create_user(username='owner', password='password123')
        self.user_two = user_model.objects.create_user(username='other', password='password123')

        category_two = Category.objects.create(user=self.user_two, name='Mercado', type=Category.Type.EXPENSE)
        self.transaction_two = Transaction.objects.create(
            user=self.user_two,
            type=Transaction.Type.EXPENSE,
            category=category_two,
            amount=Decimal('50.00'),
            date=date.today(),
            description='Compra mercado',
        )

    def test_user_cannot_update_transaction_from_other_user(self):
        self.client.login(username='owner', password='password123')
        response = self.client.get(reverse('finances:transaction_update', args=[self.transaction_two.pk]))
        self.assertEqual(response.status_code, 404)


class TransactionFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='formuser', password='password123')
        self.income_category = Category.objects.create(user=self.user, name='Salario', type=Category.Type.INCOME)
        self.expense_category = Category.objects.create(user=self.user, name='Mercado', type=Category.Type.EXPENSE)

    def test_form_initial_type_filters_categories(self):
        form = TransactionForm(user=self.user, initial={'type': Transaction.Type.INCOME})
        category_ids = list(form.fields['category'].queryset.values_list('id', flat=True))
        self.assertEqual(category_ids, [self.income_category.id])

    def test_form_post_type_filters_categories(self):
        form = TransactionForm(user=self.user, data={'type': Transaction.Type.EXPENSE})
        category_ids = list(form.fields['category'].queryset.values_list('id', flat=True))
        self.assertEqual(category_ids, [self.expense_category.id])


class ImporterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='importuser', password='password123')

    def test_category_import_creates_rows(self):
        uploaded = SimpleUploadedFile(
            'categorias.csv',
            b'name,type\nSalario,INCOME\nMercado,EXPENSE\n',
            content_type='text/csv',
        )

        report = import_categories_from_file(uploaded, self.user)

        self.assertEqual(report['created'], 2)
        self.assertEqual(Category.objects.filter(user=self.user).count(), 2)

    def test_transaction_import_creates_rows(self):
        Category.objects.create(user=self.user, name='Salario', type=Category.Type.INCOME)
        Category.objects.create(user=self.user, name='Alimentacao', type=Category.Type.EXPENSE)

        uploaded = SimpleUploadedFile(
            'lancamentos.csv',
            (
                'type,amount,date,category,description,notes,is_recurring\n'
                'INCOME,5000,2026-02-01,Salario,Recebimento,,false\n'
                'EXPENSE,120.90,2026-02-02,Alimentacao,Mercado,,false\n'
            ).encode('utf-8'),
            content_type='text/csv',
        )

        report = import_transactions_from_file(uploaded, self.user)

        self.assertEqual(report['created'], 2)
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)


class CreditCardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='carduser', password='password123')
        self.income_category = Category.objects.create(user=self.user, name='Salario', type=Category.Type.INCOME)
        self.expense_category = Category.objects.create(user=self.user, name='Mercado', type=Category.Type.EXPENSE)
        self.card = CreditCard.objects.create(user=self.user, name='Cartao Azul')

    def test_credit_card_expense_requires_expense_category(self):
        expense = CreditCardExpense(
            user=self.user,
            card=self.card,
            category=self.income_category,
            amount=Decimal('80.00'),
            date=date.today(),
        )
        with self.assertRaises(ValidationError):
            expense.full_clean()

    def test_dashboard_includes_credit_card_expenses(self):
        Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.INCOME,
            category=self.income_category,
            amount=Decimal('1000.00'),
            date=date.today(),
        )
        Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            category=self.expense_category,
            amount=Decimal('100.00'),
            date=date.today(),
        )
        CreditCardExpense.objects.create(
            user=self.user,
            card=self.card,
            category=self.expense_category,
            amount=Decimal('200.00'),
            date=date.today(),
            description='Compra no cartao',
        )

        self.client.login(username='carduser', password='password123')
        response = self.client.get(reverse('finances:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_expense'], Decimal('300.00'))
