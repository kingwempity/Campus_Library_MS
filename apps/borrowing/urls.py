from django.urls import path
from . import views

urlpatterns = [
    path('demo/', views.demo, name='borrowing_demo'),
    path('borrow/', views.borrow, name='borrow'),
    path('return/', views.return_book, name='return_book'),
    path('renew/', views.renew, name='renew'),
]


