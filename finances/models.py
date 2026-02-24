from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    class Type(models.TextChoices):
        INCOME = 'INCOME', 'Receita'
        EXPENSE = 'EXPENSE', 'Despesa'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=7, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name', 'type'], name='unique_category_per_user_and_type'),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'

    def clean(self):
        super().clean()
        if self.name:
            self.name = self.name.strip()

        if self.user_id and self.name and self.type:
            duplicated = Category.objects.filter(
                user=self.user,
                type=self.type,
                name__iexact=self.name,
            ).exclude(pk=self.pk)
            if duplicated.exists():
                raise ValidationError({'name': 'Ja existe uma categoria com este nome e tipo.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Transaction(models.Model):
    class Type(models.TextChoices):
        INCOME = 'INCOME', 'Receita'
        EXPENSE = 'EXPENSE', 'Despesa'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=7, choices=Type.choices)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.get_type_display()} - {self.amount} ({self.date})'

    def clean(self):
        super().clean()

        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'O valor deve ser maior que zero.'})

        if self.user_id and self.category_id and self.category.user_id != self.user_id:
            raise ValidationError({'category': 'Categoria invalida para este usuario.'})

        if self.category_id and self.type and self.category.type != self.type:
            raise ValidationError({'category': 'A categoria precisa ter o mesmo tipo do lancamento.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CreditCard(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='credit_cards')
    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=80, blank=True)
    last_four_digits = models.CharField(max_length=4, blank=True)
    limit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    closing_day = models.PositiveSmallIntegerField(default=1)
    due_day = models.PositiveSmallIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_credit_card_name_per_user'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.name:
            self.name = self.name.strip()

        if self.last_four_digits and (not self.last_four_digits.isdigit() or len(self.last_four_digits) != 4):
            raise ValidationError({'last_four_digits': 'Informe exatamente 4 digitos numericos.'})

        if not 1 <= self.closing_day <= 31:
            raise ValidationError({'closing_day': 'O dia de fechamento deve estar entre 1 e 31.'})

        if not 1 <= self.due_day <= 31:
            raise ValidationError({'due_day': 'O dia de vencimento deve estar entre 1 e 31.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CreditCardExpense(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='credit_card_expenses')
    card = models.ForeignKey(CreditCard, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='credit_card_expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.card.name} - {self.amount} ({self.date})'

    def clean(self):
        super().clean()

        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'O valor deve ser maior que zero.'})

        if self.user_id and self.card_id and self.card.user_id != self.user_id:
            raise ValidationError({'card': 'Cartao invalido para este usuario.'})

        if self.user_id and self.category_id and self.category.user_id != self.user_id:
            raise ValidationError({'category': 'Categoria invalida para este usuario.'})

        if self.category_id and self.category.type != Category.Type.EXPENSE:
            raise ValidationError({'category': 'Somente categorias de despesa sao permitidas no cartao.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CreditCardPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='credit_card_payments')
    card = models.ForeignKey(CreditCard, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'Pagamento {self.card.name} - {self.amount} ({self.date})'

    def clean(self):
        super().clean()

        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'O valor deve ser maior que zero.'})

        if self.user_id and self.card_id and self.card.user_id != self.user_id:
            raise ValidationError({'card': 'Cartao invalido para este usuario.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
