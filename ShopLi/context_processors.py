from .utils import get_store


def store(request):
    return {'store': get_store(request)}
