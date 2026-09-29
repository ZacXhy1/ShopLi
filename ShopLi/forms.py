from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'product_image', 'category', 'cost_price', 'selling_price', 'quantity', 'status']