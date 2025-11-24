from django.urls import path
from . import views

urlpatterns = [
    path('demo/', views.demo, name='borrowing_demo'),
    path('borrow/', views.borrow, name='borrow'),
    path('return/', views.return_book, name='return_book'),
    path('renew/', views.renew, name='renew'),
    # 逾期和罚款管理
    path('overdue/', views.overdue_management, name='overdue_management'),
    path('overdue/return/', views.return_overdue, name='return_overdue'),
    path('api/rule', views.fine_rule_api, name='fine_rule_api'),
]


