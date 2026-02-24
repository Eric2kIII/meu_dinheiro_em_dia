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
