from django.contrib import admin

from .models import Category, CreditCard, CreditCardExpense, CreditCardPayment, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'user', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('name', 'user__username')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'type', 'category', 'amount', 'user', 'is_recurring')
    list_filter = ('type', 'is_recurring', 'date')
    search_fields = ('description', 'notes', 'user__username', 'category__name')


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'last_four_digits', 'user', 'closing_day', 'due_day')
    list_filter = ('brand', 'closing_day', 'due_day')
    search_fields = ('name', 'brand', 'user__username')


@admin.register(CreditCardExpense)
class CreditCardExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'card', 'category', 'amount', 'user')
    list_filter = ('date', 'card')
    search_fields = ('description', 'notes', 'card__name', 'category__name', 'user__username')


@admin.register(CreditCardPayment)
class CreditCardPaymentAdmin(admin.ModelAdmin):
    list_display = ('date', 'card', 'amount', 'user')
    list_filter = ('date', 'card')
    search_fields = ('notes', 'card__name', 'user__username')
