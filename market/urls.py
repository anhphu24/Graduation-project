from django.urls import path

from accounts import views as account_views

from . import views

app_name = "market"

urlpatterns = [
    path("", views.lot_list, name="lot_list"),
    path("lots/<int:lot_id>/", views.lot_detail, name="lot_detail"),
    path("lots/<int:lot_id>/reserve/", views.reserve, name="reserve"),
    path("signup/", account_views.customer_signup, name="signup"),
    path("orders/", views.orders, name="orders"),
    path("orders/<uuid:order_id>/cancel/", views.cancel, name="cancel"),
    path("staff/", views.staff, name="staff"),
    path("staff/lots/new/", views.lot_new, name="lot_new"),
    path("staff/orders/<uuid:order_id>/collect/", views.collect, name="collect"),
]
