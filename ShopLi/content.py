"""Text for the About / Terms / FAQ pages and the Tutorials. Edit freely."""

ABOUT = {
    'title': 'About us',
    'intro': 'ShopLi is a simple store management system built for small business owners.',
    'sections': [
        ('What ShopLi does', 'Keep your products, stock and sales in one place: add products, watch your inventory, ring up sales at the counter, print receipts and see how your store is doing.'),
        ('Who it is for', 'Small business owners, store owners, entrepreneurs, and the cashiers and staff who help them run the day.'),
        ('Our goal', 'Take the paperwork out of running a store so you can spend your time on your customers.'),
    ],
}

TERMS = {
    'title': 'Terms and Conditions',
    'intro': 'Sample terms for a school project. Replace this text with your own before using ShopLi for a real business.',
    'sections': [
        ('1. Using ShopLi', 'You are responsible for the accuracy of the product, stock and sales information you enter, and for keeping your password private.'),
        ('2. Your data', 'The records you create belong to your store. Back up your database regularly.'),
        ('3. Acceptable use', 'Do not use ShopLi to record unlawful transactions or to store anyone\'s private information without permission.'),
        ('4. No warranty', 'ShopLi is provided as is. Always double-check totals and stock counts before relying on them for tax or accounting.'),
        ('5. Changes', 'These terms may be updated from time to time. Continuing to use ShopLi means you accept the latest version.'),
    ],
}

FAQ = {
    'title': 'Frequently asked questions',
    'intro': 'Quick answers to common questions.',
    'sections': [
        ('How do I add a product?', 'Open Product in the side menu and press + Add Product, or use the round + button on the Home page.'),
        ('How do I change the stock of an item?', 'Go to Inventory, type the new number in the Stock box on that product\'s row and press Save.'),
        ('How do I make a sale?', 'Open Home, then POS. Tap products to add them to the cart, choose a payment method and press Checkout. A receipt is created automatically.'),
        ('Why can\'t I delete a category?', 'A category can only be removed when no product uses it. Move those products to another category first.'),
        ('How do I change my currency or time zone?', 'Open the menu in the top-right corner and choose Region & Language.'),
        ('Can I print a receipt?', 'Yes. Open Home, then Receipts, choose a receipt and press Print.'),
    ],
}

PAGES = {'about': ABOUT, 'terms': TERMS, 'faq': FAQ}

TUTORIALS = [
    ('Getting started', ['Create your account and enter your store name.', 'Add your first products from the Product page.', 'Open Home, then POS, to start selling.']),
    ('Adding and editing products', ['Go to Product and press + Add Product.', 'Fill in the name, category, cost price, selling price and stock. Add a photo if you have one.', 'To change anything later, open the product card and press Save changes.']),
    ('Making a sale with POS', ['Open Home, then POS.', 'Tap a product to add it to the cart. Use + and - to change the quantity.', 'Optionally pick a customer or enter a discount.', 'Choose how the customer pays, enter the amount given for cash, then press Checkout.', 'Stock is reduced automatically and the receipt opens, ready to print.']),
    ('Keeping stock accurate', ['Open Inventory.', 'Type the real count in the Stock box of a product and press Save.', 'Items at or below their low-stock level are flagged so you know when to reorder.']),
    ('Customers and receipts', ['Add regulars under Home, then Customers.', 'Pick them in POS to link the sale to them.', 'Find any past sale under Home, then Receipts.']),
    ('Reading your analytics', ['Open Home, then Analytics and choose 7, 30 or 90 days.', 'Sales shows what came in. Profit is sales minus what the items cost you (before tax).', 'Top products and the low-stock list help you decide what to restock.']),
    ('Customizing your store', ['Open Store from the side menu.', 'Upload a logo and a banner, set your address and contact details, and choose the sales tax and receipt message.']),
]
