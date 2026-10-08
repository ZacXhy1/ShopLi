from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL

CURRENCY_CHOICES = [
    ('$', '$  US Dollar'), ('₱', '₱  Philippine Peso'), ('€', '€  Euro'),
    ('£', '£  British Pound'), ('¥', '¥  Japanese Yen'), ('S$', 'S$  Singapore Dollar'),
]
TIMEZONE_CHOICES = [
    ('UTC', 'UTC'), ('Asia/Manila', 'Philippines (Asia/Manila)'),
    ('Asia/Singapore', 'Singapore'), ('Asia/Tokyo', 'Japan'),
    ('Australia/Sydney', 'Australia (Sydney)'), ('Europe/London', 'United Kingdom'),
    ('America/New_York', 'US Eastern'), ('America/Los_Angeles', 'US Pacific'),
]
COUNTRY_CHOICES = [
    ('', 'Select a country'), ('Philippines', 'Philippines'), ('United States', 'United States'),
    ('Singapore', 'Singapore'), ('Japan', 'Japan'), ('United Kingdom', 'United Kingdom'),
    ('Australia', 'Australia'), ('Other', 'Other'),
]
LANGUAGE_CHOICES = [('en', 'English'), ('fil', 'Filipino'), ('ceb', 'Cebuano')]


class Store(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='store')
    name = models.CharField(max_length=100)
    tagline = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='store/logos/', null=True, blank=True)
    banner = models.ImageField(upload_to='store/banners/', null=True, blank=True)
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Percent added to every sale (0 for none).')
    receipt_footer = models.CharField(max_length=200, default='Thank you for shopping with us!', blank=True)
    # Region & language
    country = models.CharField(max_length=60, choices=COUNTRY_CHOICES, blank=True)
    currency = models.CharField(max_length=4, choices=CURRENCY_CHOICES, default='$')
    timezone = models.CharField(max_length=40, choices=TIMEZONE_CHOICES, default='UTC')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')

    def __str__(self):
        return self.name


class Category(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'
        unique_together = ('store', 'name')

    def __str__(self):
        return self.name


class Product(models.Model):
    PRODUCT_STATUS = [('Available', 'Available'), ('Out_of_stock', 'Out of Stock')]

    product_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    product_name = models.CharField(max_length=100)
    product_image = models.ImageField(upload_to='products/', null=True, blank=True)
    category = models.CharField(max_length=100)
    sku = models.CharField('SKU / code', max_length=40, blank=True)
    description = models.TextField(blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField('Low-stock alert at', default=5)
    date_added = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=PRODUCT_STATUS, default='Available')

    def save(self, *args, **kwargs):
        # Status is derived from stock so it never goes out of sync.
        self.status = 'Out_of_stock' if self.quantity <= 0 else 'Available'
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'status'}
        super().save(*args, **kwargs)

    @property
    def stock_state(self):
        if self.quantity <= 0:
            return 'out'
        return 'low' if self.quantity <= self.low_stock_threshold else 'ok'

    @property
    def margin(self):
        if not self.selling_price:
            return 0
        return (self.selling_price - self.cost_price) / self.selling_price * 100

    def __str__(self):
        return (f"product_id: {self.product_id}, name: {self.product_name}, price: {self.selling_price}")


class Customer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Sale(models.Model):
    PAYMENT_METHODS = [('Cash', 'Cash'), ('GCash', 'GCash / e-wallet'), ('Card', 'Card')]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='Cash')
    amount_tendered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_time', '-id']

    @property
    def receipt_no(self):
        return f"SL-{self.pk:06d}"

    def __str__(self):
        return f"{self.receipt_no} - {self.total}"


class Transaction(models.Model):
    """One line of a sale: a product, how many were sold, and the price at that moment."""
    transaction_id = models.AutoField(primary_key=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=100, blank=True)
    quantity_sold = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = self.product.product_name if self.product else self.product_name
        return (f"transaction_id: {self.transaction_id}, product: {name}, total: {self.total_amount}")


class Feedback(models.Model):
    RATINGS = [(5, '5 - Excellent'), (4, '4 - Good'), (3, '3 - Okay'), (2, '2 - Poor'), (1, '1 - Very poor')]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATINGS, default=5)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} ({self.rating}/5)"
