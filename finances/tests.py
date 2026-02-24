from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Category, Transaction


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
