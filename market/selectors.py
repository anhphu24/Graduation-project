from datetime import timedelta

from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from products.models import Lot
from products.selectors import available_lots, lot_for_display
from reservations.models import Order
from reservations.selectors import collected_revenue, orders_for_customer, orders_for_staff
from stores.selectors import all_branches, branches_in_user_scope


def market_lots(*, query="", branch_id=None, at=None):
    return available_lots(query=query, branch_id=branch_id, at=at)


def market_lot(lot_id, *, at=None):
    return lot_for_display(lot_id, at=at)


def market_branches():
    return all_branches()


def customer_orders(customer):
    return orders_for_customer(customer)


def staff_dashboard(user, *, branch_id=None):
    branches = branches_in_user_scope(user)
    if branch_id:
        branches = branches.filter(pk=branch_id)
    orders = orders_for_staff(user, branch_id=branch_id)
    horizon = timezone.now() + timedelta(days=1)
    expiring = (
        Lot.objects.filter(
            branch__in=branches,
            is_active=True,
            available_quantity__gt=0,
            expires_at__lte=horizon,
            expires_at__gte=timezone.now(),
        )
        .select_related("product", "branch")
        .order_by("expires_at", "pk")
    )
    today = timezone.localdate()
    first_date = today - timedelta(days=6)
    count_rows = (
        orders.filter(created_at__date__gte=first_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
    )
    daily_counts = {row["day"]: row["total"] for row in count_rows}
    values = [
        (first_date + timedelta(days=index), daily_counts.get(first_date + timedelta(days=index), 0))
        for index in range(7)
    ]
    max_count = max((count for _, count in values), default=0) or 1
    trend = [
        {
            "label": day.strftime("%m/%d"),
            "count": count,
            "x": 18 + 72 * index,
            "y": round(128 - (count / max_count) * 98),
        }
        for index, (day, count) in enumerate(values)
    ]
    return {
        "trend": trend,
        "trend_points": " ".join(f'{item["x"]},{item["y"]}' for item in trend),
        "orders": orders,
        "reserved_count": orders.filter(status=Order.Status.RESERVED).count(),
        "collected_count": orders.filter(status=Order.Status.COLLECTED).count(),
        "revenue": collected_revenue(orders),
        "branches": branches_in_user_scope(user),
        "expiring_count": expiring.count(),
        "expiring_lots": expiring[:5],
    }
