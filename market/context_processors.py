from django.conf import settings


def market_settings(request):
    return {"MARKET_CURRENCY": settings.CURRENCY}
