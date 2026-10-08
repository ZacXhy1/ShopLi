from .models import Product, Store


def create_store(user, name):
    """Create a user's store. The very first store adopts any products that
    were added before stores existed (e.g. the ones made in the shell)."""
    first_store = not Store.objects.exists()
    store = Store.objects.create(owner=user, name=name)
    if first_store:
        Product.objects.filter(store__isnull=True).update(store=store)
    return store


def get_store(request):
    """The logged-in user's store (created on the fly for accounts like the admin superuser)."""
    if not request.user.is_authenticated:
        return None
    if not hasattr(request, '_store'):
        try:
            request._store = request.user.store
        except Store.DoesNotExist:
            request._store = create_store(request.user, f"{request.user.username}'s Store")
    return request._store
