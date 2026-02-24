from datetime import date

from django import forms

from .models import Category, CreditCard, CreditCardExpense, CreditCardPayment, Transaction


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type']

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'Nome'
        self.fields['type'].label = 'Tipo'
        self.fields['name'].widget.attrs['class'] = 'form-control'
        self.fields['type'].widget.attrs['class'] = 'form-select'

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        category_type = cleaned_data.get('type')
        if self.user and name and category_type:
            duplicated = Category.objects.filter(
                user=self.user,
                type=category_type,
                name__iexact=name,
            ).exclude(pk=self.instance.pk)
            if duplicated.exists():
                self.add_error('name', 'Ja existe uma categoria com este nome e tipo.')
        return cleaned_data


class ImportFileForm(forms.Form):
    file = forms.FileField(label='Arquivo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs['class'] = 'form-control'

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        filename = uploaded_file.name.lower()
        if not filename.endswith('.csv') and not filename.endswith('.xlsx'):
            raise forms.ValidationError('Formato invalido. Use arquivo CSV ou XLSX.')
        return uploaded_file


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'amount', 'date', 'category', 'description', 'notes', 'is_recurring']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        self.fields['type'].label = 'Tipo'
        self.fields['amount'].label = 'Valor'
        self.fields['date'].label = 'Data'
        self.fields['category'].label = 'Categoria'
        self.fields['description'].label = 'Descricao'
        self.fields['notes'].label = 'Observacao'
        self.fields['is_recurring'].label = 'Lancamento recorrente'

        for field_name, field in self.fields.items():
            if field_name == 'is_recurring':
                field.widget.attrs['class'] = 'form-check-input'
            elif field_name in {'type', 'category'}:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

        if self.user:
            categories = Category.objects.filter(user=self.user)
        else:
            categories = Category.objects.none()

        selected_type = self.data.get('type')
        if not selected_type:
            selected_type = self.initial.get('type')
        if not selected_type and self.instance.pk:
            selected_type = self.instance.type
        if selected_type:
            categories = categories.filter(type=selected_type)
        else:
            categories = categories.none()

        self.fields['category'].queryset = categories.order_by('name')

    def clean_category(self):
        category = self.cleaned_data.get('category')
        if category and self.user and category.user_id != self.user.id:
            raise forms.ValidationError('Categoria invalida para este usuario.')
        return category

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('type')
        category = cleaned_data.get('category')

        if category and transaction_type and category.type != transaction_type:
            self.add_error('category', 'A categoria precisa ter o mesmo tipo do lancamento.')

        return cleaned_data


class CreditCardForm(forms.ModelForm):
    class Meta:
        model = CreditCard
        fields = ['name', 'brand', 'last_four_digits', 'limit_amount', 'closing_day', 'due_day']
        widgets = {
            'limit_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            'name': 'Nome do cartao',
            'brand': 'Bandeira',
            'last_four_digits': 'Ultimos 4 digitos',
            'limit_amount': 'Limite',
            'closing_day': 'Dia de fechamento',
            'due_day': 'Dia de vencimento',
        }
        for field_name, field in self.fields.items():
            field.label = labels.get(field_name, field.label)
            field.widget.attrs['class'] = 'form-control'


class CreditCardExpenseForm(forms.ModelForm):
    class Meta:
        model = CreditCardExpense
        fields = ['card', 'category', 'amount', 'date', 'description', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        self.fields['card'].label = 'Cartao'
        self.fields['category'].label = 'Categoria de despesa'
        self.fields['amount'].label = 'Valor'
        self.fields['date'].label = 'Data da compra'
        self.fields['description'].label = 'Descricao'
        self.fields['notes'].label = 'Observacao'

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        if self.user:
            self.fields['card'].queryset = CreditCard.objects.filter(user=self.user).order_by('name')
            self.fields['category'].queryset = Category.objects.filter(
                user=self.user,
                type=Category.Type.EXPENSE,
            ).order_by('name')
        else:
            self.fields['card'].queryset = CreditCard.objects.none()
            self.fields['category'].queryset = Category.objects.none()

        if not self.instance.pk and not self.initial.get('date'):
            self.initial['date'] = date.today()


class CreditCardPaymentForm(forms.ModelForm):
    class Meta:
        model = CreditCardPayment
        fields = ['card', 'amount', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        self.fields['card'].label = 'Cartao'
        self.fields['amount'].label = 'Valor pago'
        self.fields['date'].label = 'Data do pagamento'
        self.fields['notes'].label = 'Observacao'

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        if self.user:
            self.fields['card'].queryset = CreditCard.objects.filter(user=self.user).order_by('name')
        else:
            self.fields['card'].queryset = CreditCard.objects.none()

        if not self.instance.pk and not self.initial.get('date'):
            self.initial['date'] = date.today()
