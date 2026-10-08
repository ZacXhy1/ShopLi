from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def money(context, value):
    """{% money product.selling_price %} -> ₱1,234.50 (uses the store's currency)."""
    store = context.get('store')
    symbol = store.currency if store else '$'
    try:
        return f"{symbol}{Decimal(value or 0):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return f"{symbol}0.00"


@register.simple_tag
def page_numbers(page_obj):
    """Page links with '…' gaps, e.g. 1 … 4 5 6 … 20."""
    pages = page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    return [n if isinstance(n, int) else '…' for n in pages]
