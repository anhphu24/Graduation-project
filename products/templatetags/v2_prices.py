from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def discount_percent(sale_price, original_price):
    try:
        sale = Decimal(str(sale_price))
        original = Decimal(str(original_price))
        if original <= 0 or sale >= original or sale < 0:
            return 0
        return min(100, max(0, int((original - sale) * 100 / original + Decimal("0.5"))))
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
        return 0
