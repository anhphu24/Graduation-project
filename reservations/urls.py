from django.urls import path
from . import views

app_name = 'reservations'
urlpatterns = [
    path('create/', views.create, name='create'),
    path('confirm/', views.confirm, name='confirm'),
    path('history/', views.history, name='history'),
    path('cart/', views.cart, name='cart'),
]
