from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/', views.customer_login, name='login'),
    path('logout/', views.customer_logout, name='logout'),
    path('customer/login/', views.customer_login, name='customer_login'),
    path('customer/signup/', views.customer_signup, name='customer_signup'),
    path('customer/signup/success/', views.customer_signup_success, name='customer_signup_success'),
    path(
        'customer/forgot/',
        views.CustomerPasswordResetView.as_view(),
        name='customer_forgot',
    ),
    path(
        'customer/password-reset/done/',
        views.CustomerPasswordResetDoneView.as_view(),
        name='customer_password_reset_done',
    ),
    path(
        'customer/password-reset/<uidb64>/<token>/',
        views.CustomerPasswordResetConfirmView.as_view(),
        name='customer_password_reset_confirm',
    ),
    path(
        'customer/password-reset/complete/',
        views.CustomerPasswordResetCompleteView.as_view(),
        name='customer_password_reset_complete',
    ),
    path('customer/logout/', views.customer_logout, name='customer_logout'),
    path('customer/logout/complete/', views.customer_logout_complete, name='customer_logout_complete'),
    path('shop/login/', views.shop_login, name='shop_login'),
    path('shop/forgot/', views.shop_forgot, name='shop_forgot'),
    path('mypage/', views.mypage, name='mypage'),
    path('mypage/edit/', views.mypage_edit, name='mypage_edit'),
    path('mypage/password/', views.mypage_password, name='mypage_password'),
    path('mypage/delete/', views.mypage_delete, name='mypage_delete'),
]
