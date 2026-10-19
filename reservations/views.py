from django.shortcuts import render


def create(request):
    return render(request, 'reservations/create.html')


def confirm(request):
    return render(request, 'reservations/confirm.html')


def history(request):
    return render(request, 'reservations/history.html')


def cart(request):
    # UIUXデモの「カート」は仕様未確定です。
    return render(request, 'core/coming_soon.html', {'heading': 'カート（仕様確認中）'})
