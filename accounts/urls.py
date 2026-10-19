from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('customer/login/', views.customer_login, name='customer_login'),
    path('customer/signup/', views.customer_signup, name='customer_signup'),
    path('customer/forgot/', views.customer_forgot, name='customer_forgot'),
    path('customer/logout/', views.customer_logout, name='customer_logout'),
    path('shop/login/', views.shop_login, name='shop_login'),
    path('shop/forgot/', views.shop_forgot, name='shop_forgot'),
    path('mypage/', views.mypage, name='mypage'),
]
