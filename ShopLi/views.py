from django.shortcuts import render, redirect
from .models import Product
from .forms import ProductForm

# Create your views here.
def index(request):
    products = Product.objects.all()
    context = {
        'products': products
    }
    return render(request, 'Inventory/home.html', context)

def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = ProductForm()

    return render(request, 'Inventory/add_product.html', {'form': form})