from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, Customer, Feedback, Product, Store


class SignUpForm(UserCreationForm):
    store_name = forms.CharField(max_length=100, label='Store name')
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    field_order = ['store_name', 'username', 'email', 'password1', 'password2']


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'product_image', 'category', 'sku', 'description',
                  'cost_price', 'selling_price', 'quantity', 'low_stock_threshold']
        labels = {'product_name': 'Product name', 'cost_price': 'Cost price', 'selling_price': 'Selling price',
                  'quantity': 'Stock on hand'}
        widgets = {
            'category': forms.TextInput(attrs={'list': 'category-list', 'placeholder': 'Pick one or type a new category'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Size, flavour, notes for your staff...'}),
            'cost_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'quantity': forms.NumberInput(attrs={'min': '0'}),
            'low_stock_threshold': forms.NumberInput(attrs={'min': '0'}),
        }

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store

    def clean_category(self):
        return self.cleaned_data['category'].strip()

    def clean_quantity(self):
        qty = self.cleaned_data['quantity']
        if qty < 0:
            raise forms.ValidationError('Stock cannot be negative.')
        return qty

    def clean(self):
        data = super().clean()
        for name in ('cost_price', 'selling_price'):
            if data.get(name) is not None and data[name] < 0:
                self.add_error(name, 'Price cannot be negative.')
        return data

    def save(self, commit=True):
        product = super().save(commit=False)
        product.store = self.store
        if commit:
            product.save()
            Category.objects.get_or_create(store=self.store, name=product.category)
        return product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'tagline', 'description', 'address', 'phone', 'email',
                  'tax_rate', 'receipt_footer', 'logo', 'banner']
        labels = {'name': 'Store name', 'tax_rate': 'Sales tax (%)'}
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tax_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
        }


class RegionForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['country', 'currency', 'timezone', 'language']
        labels = {'timezone': 'Time zone'}


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['rating', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Tell us what is working and what is not...'})}
