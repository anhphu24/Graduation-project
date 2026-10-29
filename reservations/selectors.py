from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from stores.permissions import branches_for_user

from .models import Order


def orders_for_customer(customer):
    return Order.objects.filter(customer=customer).select_related(
        "lot", "lot__product", "lot__branch", "lot__branch__chain"
    )


def orders_for_staff(user, *, branch_id=None):
    branch_ids = branches_for_user(user).values("pk")
    orders = Order.objects.filter(lot__branch_id__in=branch_ids).select_related(
        "customer", "lot", "lot__product", "lot__branch", "collected_by"
    )
    if branch_id:
        orders = orders.filter(lot__branch_id=branch_id)
    return orders


def collected_revenue(orders):
    amount = ExpressionWrapper(
        F("quantity") * F("unit_price"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    return orders.filter(status=Order.Status.COLLECTED).aggregate(total=Sum(amount))[
        "total"
    ] or 0
