from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='dashboard_home'),
    # 统计API接口
    path('api/reports/books', views.books_statistics, name='dashboard_books_stats'),
    path('api/reports/users', views.users_statistics, name='dashboard_users_stats'),
    path('api/reports/borrows', views.borrows_statistics, name='dashboard_borrows_stats'),
    path('api/reports/summary', views.dashboard_summary, name='dashboard_summary'),
]


