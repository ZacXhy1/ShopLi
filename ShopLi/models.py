from django.db import models

# Create your models here.
class Product(models.Model):
    PRODUCT_STATUS = [('Available', 'Available'), ('Out_of_stock', 'Out of Stock')]

    product_id = models.AutoField(primary_key=True)
    product_name = models.CharField(max_length=100)
    product_image = models.ImageField(upload_to='products/', null=True, blank=True)
    category = models.CharField(max_length=100)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0)
    date_added = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=PRODUCT_STATUS, default='Available')

    def __str__(self):
        return (f"product_id: {self.product_id}, name: {self.product_name}, price: {self.selling_price}")


class Transaction(models.Model):
    transaction_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_sold = models.IntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (f"transaction_id: {self.transaction_id}, product: {self.product.product_name}, total: {self.total_amount}")