from django.urls import path
from . import views

app_name = 'products'
urlpatterns = [
    path('', views.top, name='top'),
    path('list/', views.product_list, name='list'),
    path('detail/', views.product_detail, name='detail'),
    path('recipe/', views.product_recipe, name='recipe'),
]
