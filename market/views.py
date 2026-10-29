import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import customer_required
from products.forms import LotForm
from reservations.forms import CollectOrderForm, ReserveLotForm
from stores.permissions import ensure_market_staff

from .forms import LotSearchForm
from .selectors import (
    customer_orders,
    market_branches,
    market_lot,
    market_lots,
    staff_dashboard,
)
from .services import cancel_order, collect_order, create_lot, reserve_lot


def _validation_messages(error):
    if hasattr(error, "message_dict"):
        return [message for values in error.message_dict.values() for message in values]
    if hasattr(error, "messages"):
        return error.messages
    return [str(error)]


def lot_list(request):
    form = LotSearchForm(request.GET or None, branches=market_branches())
    query = ""
    branch_id = None
    if form.is_valid():
        query = form.cleaned_data["q"]
        branch = form.cleaned_data["branch"]
        branch_id = branch.pk if branch else None
    paginator = Paginator(market_lots(query=query, branch_id=branch_id), 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "market/lot_list.html", {"form": form, "page": page})


def lot_detail(request, lot_id):
    lot = market_lot(lot_id)
    if lot is None:
        raise Http404("予約可能な商品が見つかりません。")
    form = ReserveLotForm(initial={"request_token": uuid.uuid4()})
    return render(request, "market/lot_detail.html", {"lot": lot, "form": form})


@require_POST
@customer_required
def reserve(request, lot_id):
    lot = market_lot(lot_id)
    if lot is None:
        raise Http404("予約可能な商品が見つかりません。")
    form = ReserveLotForm(request.POST)
    if form.is_valid():
        try:
            order, created = reserve_lot(
                customer=request.user,
                lot_id=lot_id,
                quantity=form.cleaned_data["quantity"],
                request_token=form.cleaned_data["request_token"],
            )
        except ValidationError as error:
            for message in _validation_messages(error):
                form.add_error(None, message)
        else:
            if created:
                messages.success(request, "商品を予約しました。受取コードをご確認ください。")
            else:
                messages.info(request, "この予約はすでに受け付けています。")
            return redirect("market:orders")
    return render(
        request,
        "market/lot_detail.html",
        {"lot": lot, "form": form},
        status=400,
    )


@customer_required
def orders(request):
    return render(
        request,
        "market/orders.html",
        {"orders": customer_orders(request.user)},
    )


@require_POST
@customer_required
def cancel(request, order_id):
    try:
        cancel_order(customer=request.user, order_id=order_id)
    except (ValidationError, PermissionDenied) as error:
        for message in _validation_messages(error):
            messages.error(request, message)
    else:
        messages.success(request, "予約をキャンセルしました。")
    return redirect("market:orders")


@login_required(login_url="accounts:customer_login")
def staff(request):
    ensure_market_staff(request.user)
    branch_id = request.GET.get("branch") or None
    if branch_id and not branch_id.isdigit():
        raise PermissionDenied("店舗の指定が正しくありません。")
    data = staff_dashboard(request.user, branch_id=branch_id)
    if branch_id and not data["branches"].filter(pk=branch_id).exists():
        raise PermissionDenied("この店舗を表示する権限がありません。")
    data.update({"selected_branch": branch_id, "collect_form": CollectOrderForm()})
    return render(request, "market/dashboard.html", data)


@login_required(login_url="accounts:customer_login")
def lot_new(request):
    ensure_market_staff(request.user)
    form = LotForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        lot = form.save(commit=False)
        try:
            create_lot(staff=request.user, lot=lot)
        except ValidationError as error:
            for message in _validation_messages(error):
                form.add_error(None, message)
        else:
            messages.success(request, "商品ロットを登録しました。")
            return redirect("market:staff")
    return render(request, "market/lot_form.html", {"form": form})


@require_POST
@login_required(login_url="accounts:customer_login")
def collect(request, order_id):
    ensure_market_staff(request.user)
    form = CollectOrderForm(request.POST)
    if not form.is_valid():
        messages.error(request, "受取コードと確認欄を入力してください。")
        return redirect("market:staff")
    try:
        collect_order(
            staff=request.user,
            order_id=order_id,
            pickup_code=form.cleaned_data["pickup_code"],
            payment_confirmed=form.cleaned_data["payment_confirmed"],
        )
    except (ValidationError, PermissionDenied) as error:
        for message in _validation_messages(error):
            messages.error(request, message)
    else:
        messages.success(request, "入金確認と商品受渡しを記録しました。")
    return redirect("market:staff")
