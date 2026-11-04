from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Report whether Django can answer requests and access its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)

    return JsonResponse({'status': 'ok'})


def index(request):
    return render(request, 'core/index.html')


def contact(request):
    return render(request, 'core/contact.html')


def shop_contact(request):
    return render(request, 'core/shop_contact.html')


def notifications(request):
    return render(request, 'core/coming_soon.html', {'heading': '通知'})
