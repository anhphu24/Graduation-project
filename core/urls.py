from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('health/', views.health, name='health'),
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('shop/contact/', views.shop_contact, name='shop_contact'),
    path('notifications/', views.notifications, name='notifications'),
]
