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
    orders = orders_for_staff(user, branch_id=branch_id)
    return {
        "orders": orders,
        "reserved_count": orders.filter(status=Order.Status.RESERVED).count(),
        "collected_count": orders.filter(status=Order.Status.COLLECTED).count(),
        "revenue": collected_revenue(orders),
        "branches": branches_in_user_scope(user),
    }
