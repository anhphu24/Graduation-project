from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.decorators import customer_required
from stores.selectors import all_branches

from .forms import ProductListFilterForm
from .selectors import available_lots


@customer_required
def top(request):
    return render(request, 'products/top.html')


def product_list(request):
    form = ProductListFilterForm(request.GET or None, branches=all_branches())
    query = ""
    branch_id = None
    if form.is_valid():
        query = form.cleaned_data["q"]
        branch = form.cleaned_data["branch"]
        branch_id = branch.pk if branch else None

    paginator = Paginator(
        available_lots(query=query, branch_id=branch_id),
        12,
    )
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "products/list.html",
        {"form": form, "page": page},
    )


def product_detail(request):
    return render(request, 'products/detail.html')

def product_recipe(request):
    return render(request, 'products/recipe.html')
