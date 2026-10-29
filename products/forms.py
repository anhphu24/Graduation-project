from django import forms

from stores.models import Branch
from stores.permissions import branches_for_user, can_manage_branch

from .models import Lot, Product


class ProductListFilterForm(forms.Form):
    q = forms.CharField(
        label="キーワード",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "商品名・店舗名で検索"}),
    )
    branch = forms.ModelChoiceField(
        label="受取店舗",
        required=False,
        queryset=Branch.objects.none(),
        empty_label="すべての店舗",
    )

    def __init__(self, *args, branches=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = (
            branches
            if branches is not None
            else Branch.objects.select_related("chain").order_by("chain__name", "name")
        )


class LotForm(forms.ModelForm):
    class Meta:
        model = Lot
        fields = (
            "branch",
            "product",
            "code",
            "original_price",
            "sale_price",
            "available_quantity",
            "reserve_start",
            "reserve_end",
            "pickup_start",
            "pickup_end",
            "expires_at",
            "is_active",
        )
        widgets = {
            "reserve_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "reserve_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "pickup_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "pickup_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        allowed_branches = branches_for_user(user)
        self.fields["branch"].queryset = allowed_branches
        chain_ids = allowed_branches.values_list("chain_id", flat=True)
        self.fields["product"].queryset = Product.objects.filter(
            chain_id__in=chain_ids
        ).select_related("chain")

    def clean(self):
        cleaned_data = super().clean()
        branch = cleaned_data.get("branch")
        product = cleaned_data.get("product")
        if branch and not can_manage_branch(self.user, branch):
            self.add_error("branch", "この店舗を操作する権限がありません。")
        if branch and product and branch.chain_id != product.chain_id:
            self.add_error("product", "店舗と同じチェーンの商品を選択してください。")
        return cleaned_data
