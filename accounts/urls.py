from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/', views.customer_login, name='login'),
    path('logout/', views.customer_logout, name='logout'),
    path('customer/login/', views.customer_login, name='customer_login'),
    path('customer/signup/', views.customer_signup, name='customer_signup'),
    path('customer/signup/success/', views.customer_signup_success, name='customer_signup_success'),
    path('customer/forgot/', views.customer_forgot, name='customer_forgot'),
    path('customer/logout/', views.customer_logout, name='customer_logout'),
    path('customer/logout/complete/', views.customer_logout_complete, name='customer_logout_complete'),
    path('shop/login/', views.shop_login, name='shop_login'),
    path('shop/forgot/', views.shop_forgot, name='shop_forgot'),
    path('mypage/', views.mypage, name='mypage'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('password/change/', views.password_change, name='password_change'),
    path('notification/settings/', views.notification_settings, name='notification_settings'),
    path('delete/', views.delete_account, name='delete_account'),
]
