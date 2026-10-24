import io
import json
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Customer, Product, Sale, Store, Transaction
from .utils import create_store

TEMP_MEDIA = tempfile.mkdtemp()


def png(name='pic.png'):
    buf = io.BytesIO()
    Image.new('RGB', (20, 20), 'brown').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ShopLiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('owner', password='pw12345!x')
        self.store = create_store(self.user, 'Test Store')
        self.client.login(username='owner', password='pw12345!x')
        self.laptop = Product.objects.create(store=self.store, product_name='Laptop', category='Electronics',
                                             cost_price=700, selling_price=1000, quantity=10)
        self.mouse = Product.objects.create(store=self.store, product_name='Mouse', category='Peripherals',
                                            cost_price=10, selling_price=25, quantity=3)

    def checkout(self, items, **extra):
        payload = {'items': items, 'payment_method': 'Cash', 'tendered': '5000', 'discount': '0', **extra}
        return self.client.post(reverse('pos_checkout'), json.dumps(payload), content_type='application/json')

    # ---- auth
    def test_login_is_the_root_page_and_logged_out_users_are_redirected(self):
        self.client.logout()
        self.assertContains(self.client.get('/'), 'Log in')
        self.assertRedirects(self.client.get(reverse('home')), '/?next=/home/')

    def test_logged_in_root_redirects_home(self):
        self.assertRedirects(self.client.get('/'), reverse('home'))

    def test_signup_requires_and_saves_store_name(self):
        self.client.logout()
        data = {'username': 'newbie', 'password1': 'Str0ng-pass-99', 'password2': 'Str0ng-pass-99'}
        self.assertEqual(self.client.post(reverse('signup'), data).status_code, 200)
        self.assertFalse(User.objects.filter(username='newbie').exists())
        resp = self.client.post(reverse('signup'), {**data, 'store_name': 'Kiosk One'})
        self.assertRedirects(resp, reverse('home'))
        self.assertEqual(User.objects.get(username='newbie').store.name, 'Kiosk One')

    def test_logout_is_post_and_returns_to_login(self):
        resp = self.client.post(reverse('logout'))
        self.assertRedirects(resp, reverse('login'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)

    def test_first_store_adopts_orphan_products(self):
        Store.objects.all().delete()
        orphan = Product.objects.create(product_name='Old', category='X', cost_price=1, selling_price=2)
        other = User.objects.create_user('first', password='x')
        create_store(other, 'First')
        orphan.refresh_from_db()
        self.assertEqual(orphan.store.owner, other)

    # ---- every page renders
    def test_all_pages_render(self):
        sale_id = self.checkout([{'id': self.laptop.pk, 'qty': 1}]).json()['url']
        urls = ['home', 'pos', 'receipts', 'customers', 'customer_add', 'calculator', 'analytics', 'tutorials',
                'inventory', 'products', 'product_add', 'store', 'profile', 'region', 'feedback', 'about', 'terms', 'faq']
        for name in urls:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(sale_id).status_code, 200)
        self.assertEqual(self.client.get(reverse('product_edit', args=[self.laptop.pk])).status_code, 200)
        for days in ('7', '30', '90'):
            self.assertEqual(self.client.get(reverse('analytics') + f'?range={days}').status_code, 200)

    def test_header_menu_and_sidebar_links(self):
        html = self.client.get(reverse('home')).content.decode()
        for text in ['Profile settings', 'About us', 'Terms and Conditions', 'Feedback', 'FAQ', 'Region &amp; Language', 'Log out',
                     'Home', 'Inventory', 'Product', 'Store']:
            self.assertIn(text, html)

    def test_home_tiles_are_in_the_requested_3x2_order_and_logo_is_used(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual([f[1] for f in resp.context['features']],
                         ['POS', 'Calculator', 'Customers', 'Receipts', 'Analytics', 'Tutorials'])
        self.assertContains(resp, 'ShopLi/logo.png')
        self.assertNotContains(resp, 'logo-ph')

    def test_fab_on_home_links_to_add_product(self):
        self.assertContains(self.client.get(reverse('home')), 'class="fab" href="/products/add/')

    # ---- POS
    def test_checkout_creates_receipt_reduces_stock_and_computes_totals(self):
        self.store.tax_rate = Decimal('10')
        self.store.save()
        customer = Customer.objects.create(store=self.store, name='Ana')
        resp = self.checkout([{'id': self.laptop.pk, 'qty': 1}, {'id': self.mouse.pk, 'qty': 2}],
                             discount='50', customer=customer.pk)
        self.assertTrue(resp.json()['ok'], resp.json())
        sale = Sale.objects.get()
        self.assertEqual((sale.subtotal, sale.discount, sale.tax, sale.total), (Decimal('1050'), Decimal('50'), Decimal('100'), Decimal('1100')))
        self.assertEqual(sale.change_due, Decimal('3900'))
        self.assertEqual(sale.customer, customer)
        self.assertEqual(Transaction.objects.filter(sale=sale).count(), 2)
        self.laptop.refresh_from_db(); self.mouse.refresh_from_db()
        self.assertEqual((self.laptop.quantity, self.mouse.quantity), (9, 1))
        self.assertContains(self.client.get(resp.json()['url']), 'SL-')

    def test_checkout_uses_server_prices_not_client_prices(self):
        resp = self.client.post(reverse('pos_checkout'), json.dumps(
            {'items': [{'id': self.laptop.pk, 'qty': 1, 'price': 1}], 'payment_method': 'Cash', 'tendered': '5000'}),
            content_type='application/json')
        self.assertEqual(Sale.objects.get().total, Decimal('1000'))

    def test_checkout_rejects_overselling_short_cash_and_empty_cart(self):
        self.assertEqual(self.checkout([{'id': self.mouse.pk, 'qty': 4}]).status_code, 400)
        self.assertEqual(self.checkout([{'id': self.laptop.pk, 'qty': 1}], tendered='10').status_code, 400)
        self.assertEqual(self.checkout([]).status_code, 400)
        self.assertEqual(self.checkout([{'id': self.laptop.pk, 'qty': 0}]).status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.quantity, 3)

    def test_selling_last_item_marks_out_of_stock(self):
        self.checkout([{'id': self.mouse.pk, 'qty': 3}])
        self.mouse.refresh_from_db()
        self.assertEqual((self.mouse.quantity, self.mouse.status), (0, 'Out_of_stock'))

    def test_cannot_sell_another_stores_product(self):
        other = create_store(User.objects.create_user('other', password='x'), 'Other')
        theirs = Product.objects.create(store=other, product_name='Secret', category='A', cost_price=1, selling_price=2, quantity=5)
        self.assertEqual(self.checkout([{'id': theirs.pk, 'qty': 1}]).status_code, 400)
        self.assertEqual(self.client.get(reverse('product_edit', args=[theirs.pk])).status_code, 404)

    # ---- inventory
    def test_inventory_paginates_at_15_and_sorts_and_searches(self):
        for i in range(20):
            Product.objects.create(store=self.store, product_name=f'Item {i:02d}', category='Bulk', cost_price=1, selling_price=2, quantity=i)
        resp = self.client.get(reverse('inventory'))
        self.assertEqual(len(resp.context['page_obj']), 15)
        self.assertEqual(resp.context['page_obj'].paginator.num_pages, 2)
        self.assertEqual(len(self.client.get(reverse('inventory') + '?page=2').context['page_obj']), 7)
        cats = [p.category for p in self.client.get(reverse('inventory') + '?sort=category&dir=desc').context['page_obj']]
        self.assertEqual(cats, sorted(cats, key=str.lower, reverse=True))
        self.assertEqual(len(self.client.get(reverse('inventory') + '?category=Electronics').context['page_obj']), 1)
        self.assertEqual(len(self.client.get(reverse('inventory') + '?q=mouse').context['page_obj']), 1)

    def test_update_stock(self):
        resp = self.client.post(reverse('update_stock', args=[self.mouse.pk]), {'quantity': '40', 'next': '/inventory/?page=1'})
        self.assertRedirects(resp, '/inventory/?page=1')
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.quantity, 40)
        self.client.post(reverse('update_stock', args=[self.mouse.pk]), {'quantity': '-5'})
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.quantity, 40)
        # open-redirect protection
        resp = self.client.post(reverse('update_stock', args=[self.mouse.pk]), {'quantity': '1', 'next': 'https://evil.example/'})
        self.assertRedirects(resp, reverse('inventory'))

    # ---- products
    def test_add_product_with_image_and_new_category(self):
        resp = self.client.post(reverse('product_add'), {
            'product_name': 'Keyboard', 'category': 'Gadgets', 'sku': 'KB-1', 'description': 'Clicky',
            'cost_price': '45', 'selling_price': '89.99', 'quantity': '25', 'low_stock_threshold': '5',
            'product_image': png()})
        self.assertRedirects(resp, reverse('products'))
        p = Product.objects.get(product_name='Keyboard')
        self.assertEqual(p.store, self.store)
        self.assertTrue(p.product_image.name.startswith('products/'))
        self.assertTrue(Category.objects.filter(store=self.store, name='Gadgets').exists())
        self.assertContains(self.client.get(reverse('products')), p.product_image.url)

    def test_product_without_image_shows_placeholder(self):
        self.assertContains(self.client.get(reverse('products')), 'No product image')

    def test_edit_product_and_remove_image(self):
        self.client.post(reverse('product_edit', args=[self.laptop.pk]), {
            'product_name': 'Laptop Pro', 'category': 'Electronics', 'cost_price': '800', 'selling_price': '1200',
            'quantity': '0', 'low_stock_threshold': '2', 'product_image': png()})
        self.laptop.refresh_from_db()
        self.assertEqual((self.laptop.product_name, self.laptop.status), ('Laptop Pro', 'Out_of_stock'))
        self.assertTrue(self.laptop.product_image)
        self.client.post(reverse('product_edit', args=[self.laptop.pk]), {
            'product_name': 'Laptop Pro', 'category': 'Electronics', 'cost_price': '800', 'selling_price': '1200',
            'quantity': '4', 'low_stock_threshold': '2', 'product_image-clear': 'on'})
        self.laptop.refresh_from_db()
        self.assertFalse(self.laptop.product_image)
        self.assertEqual(self.laptop.status, 'Available')

    def test_negative_price_rejected(self):
        resp = self.client.post(reverse('product_add'), {'product_name': 'Bad', 'category': 'X', 'cost_price': '-1',
                                                         'selling_price': '5', 'quantity': '1', 'low_stock_threshold': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Product.objects.filter(product_name='Bad').exists())

    def test_product_search_and_category_filter(self):
        resp = self.client.get(reverse('products') + '?q=lap')
        self.assertEqual([p.product_name for p in resp.context['page_obj']], ['Laptop'])
        resp = self.client.get(reverse('products') + '?category=Peripherals')
        self.assertEqual([p.product_name for p in resp.context['page_obj']], ['Mouse'])

    def test_delete_product_keeps_receipt_history(self):
        self.checkout([{'id': self.mouse.pk, 'qty': 1}])
        self.client.post(reverse('product_delete', args=[self.mouse.pk]))
        line = Transaction.objects.get()
        self.assertIsNone(line.product)
        self.assertEqual(line.product_name, 'Mouse')
        self.assertEqual(self.client.get(reverse('receipt_detail', args=[line.sale_id])).status_code, 200)

    def test_categories_add_and_guard_delete(self):
        self.client.post(reverse('category_add'), {'name': 'Snacks'})
        snacks = Category.objects.get(name='Snacks')
        self.client.post(reverse('category_delete', args=[snacks.pk]))
        self.assertFalse(Category.objects.filter(name='Snacks').exists())
        self.client.get(reverse('products'))  # syncs categories from products
        used = Category.objects.get(store=self.store, name='Electronics')
        self.client.post(reverse('category_delete', args=[used.pk]))
        self.assertTrue(Category.objects.filter(pk=used.pk).exists())

    # ---- store, customers, account
    def test_store_settings_logo_banner_and_tax(self):
        resp = self.client.post(reverse('store'), {'name': 'Renamed', 'tagline': 'Fresh', 'tax_rate': '12',
                                                   'receipt_footer': 'Bye', 'logo': png('l.png'), 'banner': png('b.png')})
        self.assertRedirects(resp, reverse('store'))
        self.store.refresh_from_db()
        self.assertEqual((self.store.name, self.store.tax_rate), ('Renamed', Decimal('12')))
        self.assertTrue(self.store.logo and self.store.banner)
        self.assertContains(self.client.get(reverse('store')), 'store-logo')

    def test_region_changes_currency(self):
        self.client.post(reverse('region'), {'country': 'Philippines', 'currency': '₱', 'timezone': 'Asia/Manila', 'language': 'en'})
        self.assertContains(self.client.get(reverse('products')), '₱1,000.00')

    def test_customer_crud(self):
        self.client.post(reverse('customer_add'), {'name': 'Ben', 'phone': '123'})
        c = Customer.objects.get(name='Ben')
        self.client.post(reverse('customer_edit', args=[c.pk]), {'name': 'Benjamin'})
        c.refresh_from_db()
        self.assertEqual(c.name, 'Benjamin')
        self.assertContains(self.client.get(reverse('customers') + '?q=benj'), 'Benjamin')
        self.client.post(reverse('customer_delete', args=[c.pk]))
        self.assertFalse(Customer.objects.exists())

    def test_profile_and_password_change_keep_you_logged_in(self):
        self.client.post(reverse('profile'), {'action': 'profile', 'first_name': 'Zed', 'last_name': 'Q', 'email': 'z@x.com'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Zed')
        self.client.post(reverse('profile'), {'action': 'password', 'old_password': 'pw12345!x',
                                              'new_password1': 'An0ther-pass-77', 'new_password2': 'An0ther-pass-77'})
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_feedback_saved(self):
        self.client.post(reverse('feedback'), {'rating': 4, 'message': 'Nice'})
        self.assertEqual(self.user.feedback_set.get().message, 'Nice')

    def test_receipts_search_and_analytics_numbers(self):
        self.store.tax_rate = Decimal('0'); self.store.save()
        self.checkout([{'id': self.laptop.pk, 'qty': 2}])
        sale = Sale.objects.get()
        self.assertEqual(len(self.client.get(reverse('receipts') + f'?q={sale.receipt_no}').context['page_obj']), 1)
        ctx = self.client.get(reverse('analytics')).context
        self.assertEqual((ctx['total'], ctx['profit'], ctx['units'], ctx['orders']), (Decimal('2000'), Decimal('600'), 2, 1))
        self.assertEqual(ctx['top'][0]['product_name'], 'Laptop')
