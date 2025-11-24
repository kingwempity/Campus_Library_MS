"""
用户认证视图模块

提供用户登录、登出和用户信息查询功能
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json


@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    用户登录视图
    
    URL: GET/POST /accounts/login/
    权限: 公开
    支持表单提交和JSON请求
    """
    # 如果已登录，重定向到首页
    if request.user.is_authenticated:
        next_url = request.GET.get('next', '/')
        return redirect(next_url)
    
    if request.method == 'POST':
        # 判断请求类型
        if request.content_type == 'application/json':
            # JSON请求
            try:
                data = json.loads(request.body)
                username = data.get('username', '')
                password = data.get('password', '')
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': '无效的JSON格式'
                    }
                }, status=400)
        else:
            # 表单请求
            username = request.POST.get('username', '')
            password = request.POST.get('password', '')
        
        # 验证用户名和密码
        if not username or not password:
            error_msg = '用户名和密码不能为空'
            if request.content_type == 'application/json':
                return JsonResponse({
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': error_msg
                    }
                }, status=400)
            return render(request, 'accounts/login.html', {
                'error': error_msg,
                'username': username
            })
        
        # 认证用户
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # 登录成功
            login(request, user)
            # 重新生成会话ID，防止会话固定攻击
            request.session.cycle_key()
            
            # JSON请求返回JSON响应
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'role': user.role,
                        'is_superuser': user.is_superuser
                    }
                })
            
            # 表单请求重定向
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            # 认证失败
            error_msg = '用户名或密码错误'
            if request.content_type == 'application/json':
                return JsonResponse({
                    'error': {
                        'code': 'AUTH_FAILED',
                        'message': error_msg
                    }
                }, status=401)
            return render(request, 'accounts/login.html', {
                'error': error_msg,
                'username': username
            })
    
    # GET请求，显示登录页面
    return render(request, 'accounts/login.html', {
        'next': request.GET.get('next', '/')
    })


@require_http_methods(["GET", "POST"])
@login_required
def logout_view(request):
    """
    用户登出视图
    
    URL: GET/POST /accounts/logout/
    权限: 已登录
    支持GET和POST请求，方便用户直接访问链接登出
    """
    logout(request)
    
    # JSON请求返回JSON响应
    if request.content_type == 'application/json':
        return JsonResponse({'success': True}, status=204)
    
    # 表单请求或GET请求重定向
    return redirect('/')


@require_http_methods(["GET"])
@login_required
def current_user(request):
    """
    获取当前用户信息API
    
    URL: GET /api/me
    权限: 已登录
    返回: 当前登录用户的信息
    """
    user = request.user
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'role': user.role,
        'role_display': dict(user.ROLE_CHOICES).get(user.role, user.role),
        'is_superuser': user.is_superuser,
        'student_id': user.student_id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name
    })
