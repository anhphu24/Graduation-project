from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Branch, Membership


def memberships_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return Membership.objects.none()
    return Membership.objects.filter(user=user).select_related("chain", "branch")


def branches_for_user(user):
    memberships = memberships_for_user(user)
    direct_branch_ids = memberships.filter(branch__isnull=False).values("branch_id")
    managed_chain_ids = memberships.filter(branch__isnull=True).values("chain_id")
    return Branch.objects.filter(
        Q(pk__in=direct_branch_ids) | Q(chain_id__in=managed_chain_ids)
    ).select_related("chain").distinct()


def can_manage_branch(user, branch):
    if not getattr(user, "is_authenticated", False):
        return False
    return Membership.objects.filter(user=user, chain=branch.chain).filter(
        Q(branch=branch) | Q(branch__isnull=True)
    ).exists()


def ensure_can_manage_branch(user, branch):
    if not can_manage_branch(user, branch):
        raise PermissionDenied("この店舗を操作する権限がありません。")


def ensure_market_staff(user):
    if not memberships_for_user(user).exists():
        raise PermissionDenied("店舗スタッフ権限がありません。")
