from django.shortcuts import render


def index(request):
    return render(request, 'core/index.html')


def contact(request):
    return render(request, 'core/contact.html')


def shop_contact(request):
    return render(request, 'core/shop_contact.html')


def notifications(request):
    return render(request, 'core/coming_soon.html', {'heading': '通知'})
