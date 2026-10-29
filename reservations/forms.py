from django import forms


class ReserveLotForm(forms.Form):
    quantity = forms.IntegerField(label="数量", min_value=1, initial=1)
    request_token = forms.UUIDField(widget=forms.HiddenInput)


class CollectOrderForm(forms.Form):
    pickup_code = forms.UUIDField(label="受取コード")
    payment_confirmed = forms.BooleanField(
        label="店頭で代金を受け取り、商品を渡しました",
        required=True,
    )
