from django.shortcuts import render
from accounts.decorators import customer_required


@customer_required
def top(request):
    return render(request, 'products/top.html')


def product_list(request):
    # 商品検索は未実装。現段階ではプレースホルダー画面を表示。
    return render(request, 'products/list.html', {'query': request.GET.get('q', '')})


def product_detail(request):
    return render(request, 'products/detail.html')
