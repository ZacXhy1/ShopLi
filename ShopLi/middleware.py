from zoneinfo import ZoneInfo

from django.utils import timezone

from .utils import get_store


class StoreTimezoneMiddleware:
    """Show dates and times in the timezone chosen on the Region & Language page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        store = get_store(request)
        try:
            timezone.activate(ZoneInfo(store.timezone) if store else timezone.get_default_timezone())
        except Exception:
            timezone.deactivate()
        return self.get_response(request)
