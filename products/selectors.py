from django.db.models import Q
from django.utils import timezone

from .models import Lot


def available_lots(*, query="", branch_id=None, at=None):
    at = at or timezone.now()
    lots = Lot.objects.select_related(
        "product",
        "product__chain",
        "branch",
        "branch__chain",
    ).filter(
        is_active=True,
        available_quantity__gt=0,
        reserve_start__lte=at,
        reserve_end__gte=at,
        pickup_end__gte=at,
        expires_at__gte=at,
    )
    if query:
        lots = lots.filter(
            Q(product__name__icontains=query)
            | Q(product__description__icontains=query)
            | Q(branch__name__icontains=query)
            | Q(branch__chain__name__icontains=query)
        )
    if branch_id:
        lots = lots.filter(branch_id=branch_id)
    return lots.order_by("reserve_end", "pk")


def lot_for_display(lot_id, *, at=None):
    return available_lots(at=at).filter(pk=lot_id).first()
