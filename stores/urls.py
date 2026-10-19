from django.urls import path
from . import views

app_name = 'stores'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('product/new/', views.product_form, name='product_form'),
]
