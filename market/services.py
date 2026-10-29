from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from products.models import Lot
from reservations.models import Order
from stores.permissions import ensure_can_manage_branch


def _ensure_customer(user):
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("ログインが必要です。")
    profile = getattr(user, "profile", None)
    if profile is None or profile.role != "customer":
        raise PermissionDenied("一般利用者アカウントが必要です。")


def create_lot(*, staff, lot):
    ensure_can_manage_branch(staff, lot.branch)
    lot.full_clean()
    with transaction.atomic():
        lot.save()
    return lot


def reserve_lot(*, customer, lot_id, quantity, request_token, at=None):
    _ensure_customer(customer)
    at = at or timezone.now()
    if quantity < 1:
        raise ValidationError("数量は1以上で指定してください。")

    with transaction.atomic():
        lot = (
            Lot.objects.select_for_update()
            .select_related("product", "branch")
            .get(pk=lot_id)
        )
        existing = Order.objects.filter(
            customer=customer,
            request_token=request_token,
        ).first()
        if existing:
            if existing.lot_id != lot.pk or existing.quantity != quantity:
                raise ValidationError("同じ送信トークンを別の予約には使用できません。")
            return existing, False

        if not lot.is_reservable_at(at):
            raise ValidationError("この商品は現在予約できません。")
        if quantity > lot.available_quantity:
            raise ValidationError("在庫数を超えて予約することはできません。")

        lot.available_quantity -= quantity
        lot.save(update_fields=("available_quantity", "updated_at"))
        order = Order(
            customer=customer,
            lot=lot,
            quantity=quantity,
            unit_price=lot.sale_price,
            request_token=request_token,
            pickup_deadline=lot.pickup_end,
        )
        order.full_clean()
        order.save()
        return order, True


def _locked_order_and_lot(order_id):
    lot_id = Order.objects.filter(pk=order_id).values_list("lot_id", flat=True).first()
    if lot_id is None:
        raise ValidationError("注文が見つかりません。")
    lot = Lot.objects.select_for_update().get(pk=lot_id)
    order = Order.objects.select_for_update().select_related("lot__branch").get(pk=order_id)
    return order, lot


def cancel_order(*, customer, order_id, at=None):
    _ensure_customer(customer)
    at = at or timezone.now()
    with transaction.atomic():
        order, lot = _locked_order_and_lot(order_id)
        if order.customer_id != customer.pk:
            raise PermissionDenied("この注文をキャンセルする権限がありません。")
        if order.status != Order.Status.RESERVED:
            raise ValidationError("予約済みの注文だけキャンセルできます。")
        if at >= order.pickup_deadline:
            raise ValidationError("受取期限を過ぎた注文はキャンセルできません。")

        lot.available_quantity += order.quantity
        lot.save(update_fields=("available_quantity", "updated_at"))
        order.status = Order.Status.CANCELLED
        order.save(update_fields=("status",))
        return order


def collect_order(*, staff, order_id, pickup_code, payment_confirmed, at=None):
    if not payment_confirmed:
        raise ValidationError("代金受領と商品受渡しの確認が必要です。")
    at = at or timezone.now()
    with transaction.atomic():
        order, lot = _locked_order_and_lot(order_id)
        ensure_can_manage_branch(staff, lot.branch)
        if order.status != Order.Status.RESERVED:
            raise ValidationError("予約済みの注文だけ受取処理できます。")
        if order.pickup_code != pickup_code:
            raise ValidationError("受取コードが一致しません。")
        if at < lot.pickup_start or at > order.pickup_deadline:
            raise ValidationError("現在は受取可能時間ではありません。")
        if at > lot.expires_at:
            raise ValidationError("商品の期限を過ぎているため受け渡しできません。")

        order.status = Order.Status.COLLECTED
        order.paid_at = at
        order.collected_by = staff
        order.full_clean()
        order.save(update_fields=("status", "paid_at", "collected_by"))
        return order


def expire_order(*, order_id, at=None):
    at = at or timezone.now()
    with transaction.atomic():
        order, lot = _locked_order_and_lot(order_id)
        if order.status != Order.Status.RESERVED or order.pickup_deadline >= at:
            return False
        lot.available_quantity += order.quantity
        lot.save(update_fields=("available_quantity", "updated_at"))
        order.status = Order.Status.EXPIRED
        order.save(update_fields=("status",))
        return True


def expire_orders(*, batch_size=100, at=None):
    at = at or timezone.now()
    order_ids = list(
        Order.objects.filter(
            status=Order.Status.RESERVED,
            pickup_deadline__lt=at,
        )
        .order_by("pickup_deadline")
        .values_list("pk", flat=True)[:batch_size]
    )
    return sum(expire_order(order_id=order_id, at=at) for order_id in order_ids)


def seed_demo_data(*, at=None):
    """Create repeatable demo catalog data without accounts or passwords."""
    from products.models import Product
    from stores.models import Branch, Chain

    at = at or timezone.now()
    created = {"chains": 0, "branches": 0, "products": 0, "lots": 0}
    with transaction.atomic():
        chain, was_created = Chain.objects.get_or_create(name="フードレスキューマート")
        created["chains"] += int(was_created)
        branch_specs = (
            ("駅前店", "東京都千代田区1-1"),
            ("中央店", "東京都中央区2-2"),
        )
        branches = []
        for name, address in branch_specs:
            branch, was_created = Branch.objects.get_or_create(
                chain=chain,
                name=name,
                defaults={"address": address},
            )
            created["branches"] += int(was_created)
            branches.append(branch)

        product_specs = (
            ("レスキューパンセット", "当日焼き上げたパンの詰め合わせ", "小麦・乳", "常温"),
            ("季節の野菜セット", "まだおいしく食べられる季節の野菜", "", "冷蔵"),
            ("お弁当セット", "店頭調理のお弁当", "小麦・卵・大豆", "要冷蔵"),
        )
        products = []
        for name, description, allergens, storage in product_specs:
            product, was_created = Product.objects.get_or_create(
                chain=chain,
                name=name,
                defaults={
                    "description": description,
                    "allergens": allergens,
                    "storage_instructions": storage,
                },
            )
            created["products"] += int(was_created)
            products.append(product)

        for index, product in enumerate(products, start=1):
            branch = branches[(index - 1) % len(branches)]
            code = f"DEMO-{index:03d}"
            if Lot.objects.filter(branch=branch, code=code).exists():
                continue
            lot = Lot(
                product=product,
                branch=branch,
                code=code,
                original_price=Decimal("600"),
                sale_price=Decimal("300"),
                available_quantity=10,
                reserve_start=at - timedelta(hours=1),
                reserve_end=at + timedelta(hours=8),
                pickup_start=at,
                pickup_end=at + timedelta(hours=10),
                expires_at=at + timedelta(hours=12),
            )
            lot.full_clean()
            lot.save()
            created["lots"] += 1
    return created
