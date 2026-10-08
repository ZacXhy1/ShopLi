import json
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Lower, TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .content import PAGES, TUTORIALS
from .forms import (CategoryForm, CustomerForm, FeedbackForm, ProductForm, ProfileForm,
                    RegionForm, SignUpForm, StoreForm)
from .models import Category, Customer, Product, Sale, Transaction
from .utils import create_store, get_store

CENTS = Decimal('0.01')


# ---------------------------------------------------------------- helpers
def safe_next(request, default):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


def paginate(request, queryset, per_page):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def qs_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def sync_categories(store):
    """Make sure every category used by a product also exists in the Category list."""
    used = set(Product.objects.filter(store=store).exclude(category='').values_list('category', flat=True))
    known = set(Category.objects.filter(store=store).values_list('name', flat=True))
    Category.objects.bulk_create([Category(store=store, name=n) for n in used - known])


def money_value(raw, default='0'):
    try:
        return Decimal(str(raw if raw not in (None, '') else default)).quantize(CENTS, ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError('Please enter valid amounts.')


# ---------------------------------------------------------------- auth
def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            create_store(user, form.cleaned_data['store_name'])
        login(request, user)
        messages.success(request, f"Welcome to ShopLi! {form.cleaned_data['store_name']} is ready.")
        return redirect('home')
    return render(request, 'ShopLi/auth/signup.html', {'form': form})


# ---------------------------------------------------------------- home
@login_required
def home(request):
    store = get_store(request)
    today_sales = Sale.objects.filter(store=store, date_time__date=timezone.localdate())
    today = today_sales.aggregate(total=Sum('total'), orders=Count('id'))
    products = Product.objects.filter(store=store)
    context = {
        'today_total': today['total'] or 0,
        'today_orders': today['orders'],
        'product_count': products.count(),
        'low_stock': products.filter(quantity__lte=F('low_stock_threshold')).count(),
        'recent': Sale.objects.filter(store=store).select_related('customer')[:5],
        'features': [
            ('pos', 'POS', 'Ring up a sale at the counter.', '🛒'),
            ('receipts', 'Receipts', 'Look up and print past sales.', '🧾'),
            ('customers', 'Customers', 'Keep your regulars in one list.', '👥'),
            ('calculator', 'Calculator', 'Quick math without leaving ShopLi.', '🧮'),
            ('analytics', 'Analytics', 'Sales, profit and top sellers.', '📊'),
            ('tutorials', 'Tutorials', 'Step-by-step guides.', '🎓'),
        ],
    }
    return render(request, 'ShopLi/home/home.html', context)


@login_required
def pos(request):
    store = get_store(request)
    sync_categories(store)
    return render(request, 'ShopLi/home/pos.html', {
        'products': Product.objects.filter(store=store).order_by(Lower('category'), Lower('product_name')),
        'categories': Category.objects.filter(store=store),
        'customers': Customer.objects.filter(store=store),
        'payment_methods': Sale.PAYMENT_METHODS,
    })


@login_required
@require_POST
def pos_checkout(request):
    store = get_store(request)
    try:
        data = json.loads(request.body)
        wanted = defaultdict(int)
        for line in data.get('items', []):
            qty = int(line['qty'])
            if qty < 1:
                raise ValueError
            wanted[int(line['id'])] += qty
        if not wanted:
            return JsonResponse({'ok': False, 'error': 'The cart is empty.'}, status=400)
        discount = money_value(data.get('discount'))
        tendered = money_value(data.get('tendered'))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'ok': False, 'error': 'That order could not be read. Please try again.'}, status=400)

    method = data.get('payment_method', 'Cash')
    if method not in dict(Sale.PAYMENT_METHODS):
        return JsonResponse({'ok': False, 'error': 'Choose a valid payment method.'}, status=400)

    with transaction.atomic():
        products = {p.pk: p for p in Product.objects.select_for_update().filter(store=store, pk__in=wanted)}
        if len(products) != len(wanted):
            return JsonResponse({'ok': False, 'error': 'A product in the cart no longer exists.'}, status=400)
        subtotal = Decimal('0')
        for pk, qty in wanted.items():
            p = products[pk]
            if qty > p.quantity:
                return JsonResponse({'ok': False, 'error': f'Only {p.quantity} of "{p.product_name}" left in stock.'}, status=400)
            subtotal += p.selling_price * qty
        discount = max(Decimal('0'), min(discount, subtotal))
        tax = ((subtotal - discount) * store.tax_rate / 100).quantize(CENTS, ROUND_HALF_UP)
        total = subtotal - discount + tax
        if method == 'Cash':
            if tendered < total:
                return JsonResponse({'ok': False, 'error': 'The cash received is less than the total.'}, status=400)
            change = tendered - total
        else:
            tendered, change = total, Decimal('0')

        customer = None
        if data.get('customer'):
            customer = Customer.objects.filter(store=store, pk=data['customer']).first()
        sale = Sale.objects.create(store=store, customer=customer, cashier=request.user, subtotal=subtotal,
                                   discount=discount, tax=tax, total=total, payment_method=method,
                                   amount_tendered=tendered, change_due=change)
        lines = []
        for pk, qty in wanted.items():
            p = products[pk]
            lines.append(Transaction(sale=sale, product=p, product_name=p.product_name, quantity_sold=qty,
                                     unit_price=p.selling_price, unit_cost=p.cost_price,
                                     total_amount=p.selling_price * qty))
            p.quantity -= qty
            p.save(update_fields=['quantity'])
        Transaction.objects.bulk_create(lines)

    return JsonResponse({'ok': True, 'url': reverse('receipt_detail', args=[sale.pk]) + '?new=1'})


@login_required
def receipts(request):
    store = get_store(request)
    sales = Sale.objects.filter(store=store).select_related('customer').annotate(item_count=Sum('items__quantity_sold'))
    q = request.GET.get('q', '').strip()
    if q:
        digits = ''.join(ch for ch in q if ch.isdigit())
        cond = Q(customer__name__icontains=q)
        if digits:
            cond |= Q(pk=int(digits))
        sales = sales.filter(cond)
    return render(request, 'ShopLi/home/receipts.html', {'page_obj': paginate(request, sales, 15), 'q': q,
                                                          'qs': qs_without_page(request)})


@login_required
def receipt_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer', 'cashier'), pk=pk, store=get_store(request))
    return render(request, 'ShopLi/home/receipt_detail.html', {'sale': sale, 'items': sale.items.all(), 'is_new': 'new' in request.GET})


@login_required
def customers(request):
    store = get_store(request)
    qs = Customer.objects.filter(store=store).annotate(orders=Count('sale'), spent=Sum('sale__total'))
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    return render(request, 'ShopLi/home/customers.html', {'page_obj': paginate(request, qs, 15), 'q': q,
                                                           'qs': qs_without_page(request)})


@login_required
def customer_form(request, pk=None):
    store = get_store(request)
    customer = get_object_or_404(Customer, pk=pk, store=store) if pk else None
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.store = store
        obj.save()
        messages.success(request, f'Customer "{obj.name}" saved.')
        return redirect('customers')
    return render(request, 'ShopLi/home/customer_form.html', {'form': form, 'customer': customer})


@login_required
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk, store=get_store(request))
    customer.delete()
    messages.success(request, f'Customer "{customer.name}" deleted. Their past receipts are kept.')
    return redirect('customers')


@login_required
def calculator(request):
    return render(request, 'ShopLi/home/calculator.html')


@login_required
def analytics(request):
    store = get_store(request)
    days = {'7': 7, '30': 30, '90': 90}.get(request.GET.get('range'), 7)
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    sales = Sale.objects.filter(store=store, date_time__date__gte=start)
    lines = Transaction.objects.filter(sale__in=sales)

    s = sales.aggregate(total=Sum('total'), subtotal=Sum('subtotal'), discount=Sum('discount'), orders=Count('id'))
    cost_expr = ExpressionWrapper(F('unit_cost') * F('quantity_sold'), output_field=DecimalField())
    l = lines.aggregate(units=Sum('quantity_sold'), cost=Sum(cost_expr))
    total, orders = s['total'] or Decimal('0'), s['orders']
    net = (s['subtotal'] or Decimal('0')) - (s['discount'] or Decimal('0'))
    profit = net - (l['cost'] or Decimal('0'))

    per_day = {r['day']: r['t'] for r in sales.annotate(day=TruncDate('date_time')).values('day').annotate(t=Sum('total'))}
    series = [(start + timedelta(days=i), per_day.get(start + timedelta(days=i), Decimal('0'))) for i in range(days)]
    peak = max((v for _, v in series), default=0) or 1
    step = 1 if days <= 7 else (5 if days <= 30 else 15)
    bars = [{'label': d.strftime('%a %d') if days <= 7 else d.strftime('%b %d'), 'value': v,
             'pct': float(v / peak * 100), 'show': i % step == 0} for i, (d, v) in enumerate(series)]

    top = lines.values('product_name').annotate(units=Sum('quantity_sold'), revenue=Sum('total_amount')).order_by('-units')[:5]
    by_cat = list(lines.values('product__category').annotate(revenue=Sum('total_amount')).order_by('-revenue')[:6])
    cat_peak = max((c['revenue'] for c in by_cat), default=0) or 1
    for c in by_cat:
        c['name'] = c['product__category'] or 'Uncategorized'
        c['pct'] = float(c['revenue'] / cat_peak * 100)

    return render(request, 'ShopLi/home/analytics.html', {
        'days': days, 'total': total, 'orders': orders, 'units': l['units'] or 0, 'profit': profit,
        'average': (total / orders) if orders else 0, 'bars': bars, 'top': top, 'by_cat': by_cat,
        'low_stock': Product.objects.filter(store=store, quantity__lte=F('low_stock_threshold')).order_by('quantity')[:8],
    })


@login_required
def tutorials(request):
    return render(request, 'ShopLi/home/tutorials.html', {'tutorials': TUTORIALS})


# ---------------------------------------------------------------- inventory
SORT_FIELDS = {'id': 'product_id', 'name': 'product_name', 'category': 'category', 'price': 'selling_price', 'stock': 'quantity'}


@login_required
def inventory(request):
    store = get_store(request)
    sync_categories(store)
    all_products = Product.objects.filter(store=store)
    qs = all_products
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    if q:
        qs = qs.filter(Q(product_name__icontains=q) | Q(sku__icontains=q) | Q(category__icontains=q))
    if category:
        qs = qs.filter(category=category)

    sort = request.GET.get('sort') if request.GET.get('sort') in SORT_FIELDS else 'name'
    direction = 'desc' if request.GET.get('dir') == 'desc' else 'asc'
    field = SORT_FIELDS[sort]
    order = Lower(field) if sort in ('name', 'category') else F(field)
    order = order.desc() if direction == 'desc' else order.asc()
    qs = qs.order_by(order, Lower('product_name'))

    headers = []
    for key, label in [('id', 'ID'), ('name', 'Product'), ('category', 'Category'), ('price', 'Price'), ('stock', 'Stock')]:
        params = request.GET.copy()
        params.pop('page', None)
        params['sort'] = key
        params['dir'] = 'desc' if (sort == key and direction == 'asc') else 'asc'
        headers.append({'label': label, 'url': '?' + params.urlencode(), 'active': sort == key,
                        'arrow': '▲' if direction == 'asc' else '▼'})

    value = ExpressionWrapper(F('cost_price') * F('quantity'), output_field=DecimalField())
    stats = all_products.aggregate(units=Sum('quantity'), value=Sum(value))
    return render(request, 'ShopLi/inventory/inventory.html', {
        'page_obj': paginate(request, qs, 15), 'q': q, 'category': category, 'headers': headers,
        'sort': sort, 'dir': direction, 'qs': qs_without_page(request),
        'categories': Category.objects.filter(store=store),
        'total_products': all_products.count(), 'total_units': stats['units'] or 0, 'stock_value': stats['value'] or 0,
        'low_count': all_products.filter(quantity__gt=0, quantity__lte=F('low_stock_threshold')).count(),
        'out_count': all_products.filter(quantity__lte=0).count(),
    })


@login_required
@require_POST
def update_stock(request, pk):
    product = get_object_or_404(Product, pk=pk, store=get_store(request))
    try:
        qty = int(request.POST.get('quantity', ''))
        if qty < 0:
            raise ValueError
    except ValueError:
        messages.error(request, 'Stock must be a whole number, 0 or higher.')
    else:
        product.quantity = qty
        product.save()
        messages.success(request, f'Stock for "{product.product_name}" set to {qty}.')
    return redirect(safe_next(request, reverse('inventory')))


# ---------------------------------------------------------------- products
@login_required
def products(request):
    store = get_store(request)
    sync_categories(store)
    all_products = Product.objects.filter(store=store)
    qs = all_products.order_by(Lower('product_name'))
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    if q:
        qs = qs.filter(Q(product_name__icontains=q) | Q(sku__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category=category)
    counts = dict(all_products.values_list('category').annotate(n=Count('pk')))
    cats = [{'obj': c, 'count': counts.get(c.name, 0)} for c in Category.objects.filter(store=store)]
    return render(request, 'ShopLi/products/products.html', {
        'page_obj': paginate(request, qs, 12), 'q': q, 'category': category, 'cats': cats,
        'qs': qs_without_page(request), 'total': all_products.count(),
    })


@login_required
def product_form(request, pk=None):
    store = get_store(request)
    sync_categories(store)
    product = get_object_or_404(Product, pk=pk, store=store) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product, store=store)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, f'"{saved.product_name}" was {"updated" if product else "added"}.')
        return redirect(safe_next(request, reverse('products')))
    return render(request, 'ShopLi/products/product_form.html', {
        'form': form, 'product': product, 'categories': Category.objects.filter(store=store),
        'next': safe_next(request, ''),
    })


@login_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, store=get_store(request))
    product.delete()
    messages.success(request, f'"{product.product_name}" was deleted. Past receipts keep their record of it.')
    return redirect('products')


@login_required
@require_POST
def category_add(request):
    store = get_store(request)
    form = CategoryForm(request.POST)
    name = form.data.get('name', '').strip()
    if not name:
        messages.error(request, 'Type a category name first.')
    elif Category.objects.filter(store=store, name__iexact=name).exists():
        messages.error(request, f'"{name}" already exists.')
    else:
        Category.objects.create(store=store, name=name[:100])
        messages.success(request, f'Category "{name}" added.')
    return redirect(safe_next(request, reverse('products')))


@login_required
@require_POST
def category_delete(request, pk):
    store = get_store(request)
    category = get_object_or_404(Category, pk=pk, store=store)
    if Product.objects.filter(store=store, category=category.name).exists():
        messages.error(request, f'"{category.name}" is still used by some products. Move them first.')
    else:
        category.delete()
        messages.success(request, f'Category "{category.name}" deleted.')
    return redirect('products')


# ---------------------------------------------------------------- store
@login_required
def store_settings(request):
    store = get_store(request)
    form = StoreForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Store settings saved.')
        return redirect('store')
    return render(request, 'ShopLi/store/store.html', {
        'form': form, 'product_count': Product.objects.filter(store=store).count(),
        'sale_count': Sale.objects.filter(store=store).count(),
        'customer_count': Customer.objects.filter(store=store).count(),
    })


# ---------------------------------------------------------------- account & info pages
@login_required
def profile(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)
    if request.method == 'POST':
        if request.POST.get('action') == 'password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed.')
                return redirect('profile')
        else:
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('profile')
    return render(request, 'ShopLi/account/profile.html', {'profile_form': profile_form, 'password_form': password_form})


@login_required
def region(request):
    form = RegionForm(request.POST or None, instance=get_store(request))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Region & language saved.')
        return redirect('region')
    return render(request, 'ShopLi/account/region.html', {'form': form})


@login_required
def feedback(request):
    form = FeedbackForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.user = request.user
        entry.save()
        messages.success(request, 'Thank you! Your feedback was sent.')
        return redirect('feedback')
    return render(request, 'ShopLi/account/feedback.html', {'form': form})


@login_required
def info(request, page):
    return render(request, 'ShopLi/account/info.html', {'page': PAGES[page], 'slug': page})
