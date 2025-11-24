"""
用户认证URL配置
"""
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/me', views.current_user, name='current_user'),
]

