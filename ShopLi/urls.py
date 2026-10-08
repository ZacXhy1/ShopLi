from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # Login is the first page you see at http://127.0.0.1:8000/
    path('', auth_views.LoginView.as_view(template_name='ShopLi/auth/login.html', redirect_authenticated_user=True), name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Home
    path('home/', views.home, name='home'),
    path('home/pos/', views.pos, name='pos'),
    path('home/pos/checkout/', views.pos_checkout, name='pos_checkout'),
    path('home/receipts/', views.receipts, name='receipts'),
    path('home/receipts/<int:pk>/', views.receipt_detail, name='receipt_detail'),
    path('home/customers/', views.customers, name='customers'),
    path('home/customers/add/', views.customer_form, name='customer_add'),
    path('home/customers/<int:pk>/edit/', views.customer_form, name='customer_edit'),
    path('home/customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    path('home/calculator/', views.calculator, name='calculator'),
    path('home/analytics/', views.analytics, name='analytics'),
    path('home/tutorials/', views.tutorials, name='tutorials'),

    # Inventory
    path('inventory/', views.inventory, name='inventory'),
    path('inventory/<int:pk>/stock/', views.update_stock, name='update_stock'),

    # Product
    path('products/', views.products, name='products'),
    path('products/add/', views.product_form, name='product_add'),
    path('products/<int:pk>/edit/', views.product_form, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/categories/add/', views.category_add, name='category_add'),
    path('products/categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Store
    path('store/', views.store_settings, name='store'),

    # Header menu
    path('account/profile/', views.profile, name='profile'),
    path('account/region/', views.region, name='region'),
    path('feedback/', views.feedback, name='feedback'),
    path('about/', views.info, {'page': 'about'}, name='about'),
    path('terms/', views.info, {'page': 'terms'}, name='terms'),
    path('faq/', views.info, {'page': 'faq'}, name='faq'),
]
