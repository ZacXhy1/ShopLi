from django.contrib import admin

from .models import Category, Customer, Feedback, Product, Sale, Store, Transaction

for model in (Store, Category, Product, Customer, Sale, Transaction, Feedback):
    admin.site.register(model)
