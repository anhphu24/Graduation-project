from django.shortcuts import render


def dashboard(request):
    return render(request, 'stores/dashboard.html')


def product_form(request):
    return render(request, 'stores/product_form.html')
