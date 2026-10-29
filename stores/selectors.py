from .models import Branch
from .permissions import branches_for_user, memberships_for_user


def all_branches():
    return Branch.objects.select_related("chain").order_by("chain__name", "name")


def branches_in_user_scope(user):
    return branches_for_user(user).order_by("chain__name", "name")


def memberships_in_user_scope(user):
    return memberships_for_user(user).order_by("chain__name", "branch__name")
