"""
Dashboard数据统计视图模块

提供系统运营数据的统计分析和可视化展示功能，包括：
- 图书统计：总数、可借数量、分类分布、热门图书排行
- 用户统计：注册用户数、活跃用户数、逾期用户数、借阅量排行
- 借阅趋势：按日/周/月聚合的借阅与归还趋势数据
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from apps.library.models import Book
from apps.borrowing.models import BorrowRecord
from apps.accounts.models import User


def _check_admin_permission(user):
    """检查用户是否为管理员"""
    if not user.is_authenticated:
        return False
    return user.role == 'admin' or user.is_superuser


@login_required
def home(request):
    """Dashboard首页视图"""
    # 如果是管理员，显示统计页面；否则显示普通首页
    if _check_admin_permission(request.user):
        return render(request, 'dashboard/index.html', {
            'is_admin': True,
        })
    return render(request, 'dashboard/index.html', {
        'is_admin': False,
    })


@require_http_methods(["GET"])
@login_required
def books_statistics(request):
    """
    图书统计API
    
    URL: GET /api/reports/books
    权限: admin
    返回: 图书总数、可借数量、各分类分布、热门图书排行（按借阅次数）
    """
    if not _check_admin_permission(request.user):
        return JsonResponse({
            'error': {
                'code': 'FORBIDDEN',
                'message': '无权限访问此接口'
            }
        }, status=403)
    
    try:
        # 基础统计
        total_books = Book.objects.count()
        total_copies = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
        available_copies = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
        borrowed_copies = total_copies - available_copies
        
        # 分类分布统计
        category_stats = Book.objects.values('category').annotate(
            count=Count('id'),
            total_copies=Sum('total_copies'),
            available_copies=Sum('available_copies')
        ).order_by('-count')
        
        category_distribution = [
            {
                'category': item['category'] or '未分类',
                'count': item['count'],
                'total_copies': item['total_copies'],
                'available_copies': item['available_copies']
            }
            for item in category_stats
        ]
        
        # 热门图书排行（按借阅次数）
        popular_books = Book.objects.annotate(
            borrow_count=Count('borrow_records')
        ).order_by('-borrow_count')[:10]
        
        popular_books_list = [
            {
                'id': book.id,
                'title': book.title,
                'author': book.author,
                'isbn': book.isbn,
                'category': book.category,
                'borrow_count': book.borrow_count,
                'available_copies': book.available_copies,
                'total_copies': book.total_copies
            }
            for book in popular_books
        ]
        
        return JsonResponse({
            'total_books': total_books,
            'total_copies': total_copies,
            'available_copies': available_copies,
            'borrowed_copies': borrowed_copies,
            'category_distribution': category_distribution,
            'popular_books': popular_books_list
        })
    
    except Exception as e:
        return JsonResponse({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': f'统计计算失败: {str(e)}'
            }
        }, status=500)


@require_http_methods(["GET"])
@login_required
def users_statistics(request):
    """
    用户统计API
    
    URL: GET /api/reports/users
    权限: admin
    返回: 注册用户数、活跃用户数、逾期用户数、借阅量排行
    """
    if not _check_admin_permission(request.user):
        return JsonResponse({
            'error': {
                'code': 'FORBIDDEN',
                'message': '无权限访问此接口'
            }
        }, status=403)
    
    try:
        # 基础统计
        total_users = User.objects.count()
        
        # 按角色统计
        role_stats = User.objects.values('role').annotate(
            count=Count('id')
        ).order_by('-count')
        
        role_distribution = [
            {
                'role': item['role'],
                'role_display': dict(User.ROLE_CHOICES).get(item['role'], item['role']),
                'count': item['count']
            }
            for item in role_stats
        ]
        
        # 活跃用户数（最近30天内有借阅记录的用户）
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_users = User.objects.filter(
            borrow_records__borrowed_at__gte=thirty_days_ago
        ).distinct().count()
        
        # 逾期用户数（当前有逾期未还记录的用户）
        overdue_users = User.objects.filter(
            borrow_records__status='overdue'
        ).distinct().count()
        
        # 用户借阅量排行（按借阅记录总数）
        top_borrowers = User.objects.annotate(
            borrow_count=Count('borrow_records')
        ).filter(borrow_count__gt=0).order_by('-borrow_count')[:10]
        
        top_borrowers_list = [
            {
                'id': user.id,
                'username': user.username,
                'student_id': user.student_id,
                'role': user.role,
                'borrow_count': user.borrow_count
            }
            for user in top_borrowers
        ]
        
        return JsonResponse({
            'total_users': total_users,
            'active_users': active_users,
            'overdue_users': overdue_users,
            'role_distribution': role_distribution,
            'top_borrowers': top_borrowers_list
        })
    
    except Exception as e:
        return JsonResponse({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': f'统计计算失败: {str(e)}'
            }
        }, status=500)


@require_http_methods(["GET"])
@login_required
def borrows_statistics(request):
    """
    借阅趋势统计API
    
    URL: GET /api/reports/borrows
    权限: admin
    查询参数:
        - period: 统计周期，可选值: 'day'（日）、'week'（周）、'month'（月），默认 'day'
        - days: 统计天数范围，默认 30
    返回: 按日/周/月聚合的借阅与归还趋势数据
    """
    if not _check_admin_permission(request.user):
        return JsonResponse({
            'error': {
                'code': 'FORBIDDEN',
                'message': '无权限访问此接口'
            }
        }, status=403)
    
    try:
        period = request.GET.get('period', 'day')  # day, week, month
        days = int(request.GET.get('days', 30))
        
        # 计算时间范围
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # 基础统计
        total_borrows = BorrowRecord.objects.filter(
            borrowed_at__gte=start_date
        ).count()
        
        total_returns = BorrowRecord.objects.filter(
            returned_at__gte=start_date,
            status='returned'
        ).count()
        
        current_borrows = BorrowRecord.objects.filter(
            status='borrowed'
        ).count()
        
        overdue_count = BorrowRecord.objects.filter(
            status='overdue'
        ).count()
        
        total_fines = BorrowRecord.objects.filter(
            fine_amount__gt=0
        ).aggregate(total=Sum('fine_amount'))['total'] or Decimal('0.00')
        
        # 按周期聚合借阅趋势
        borrow_trend = []
        return_trend = []
        
        if period == 'day':
            # 按日统计
            current = start_date.date()
            end = end_date.date()
            while current <= end:
                day_start = timezone.make_aware(datetime.combine(current, datetime.min.time()))
                day_end = day_start + timedelta(days=1)
                
                borrow_count = BorrowRecord.objects.filter(
                    borrowed_at__gte=day_start,
                    borrowed_at__lt=day_end
                ).count()
                
                return_count = BorrowRecord.objects.filter(
                    returned_at__gte=day_start,
                    returned_at__lt=day_end,
                    status='returned'
                ).count()
                
                borrow_trend.append({
                    'date': current.isoformat(),
                    'count': borrow_count
                })
                
                return_trend.append({
                    'date': current.isoformat(),
                    'count': return_count
                })
                
                current += timedelta(days=1)
        
        elif period == 'week':
            # 按周统计
            current = start_date.date()
            end = end_date.date()
            week_start = current
            while current <= end:
                # 每周一作为周的开始
                if current.weekday() == 0 or current == start_date.date():
                    week_start = current
                
                # 如果是周日或者是最后一天，统计这一周
                if current.weekday() == 6 or current == end:
                    week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
                    week_end_dt = timezone.make_aware(datetime.combine(current + timedelta(days=1), datetime.min.time()))
                    
                    borrow_count = BorrowRecord.objects.filter(
                        borrowed_at__gte=week_start_dt,
                        borrowed_at__lt=week_end_dt
                    ).count()
                    
                    return_count = BorrowRecord.objects.filter(
                        returned_at__gte=week_start_dt,
                        returned_at__lt=week_end_dt,
                        status='returned'
                    ).count()
                    
                    borrow_trend.append({
                        'date': week_start.isoformat(),
                        'count': borrow_count
                    })
                    
                    return_trend.append({
                        'date': week_start.isoformat(),
                        'count': return_count
                    })
                
                current += timedelta(days=1)
        
        elif period == 'month':
            # 按月统计
            current = start_date.date().replace(day=1)
            end = end_date.date()
            while current <= end:
                month_start = current
                # 计算下个月的第一天
                if month_start.month == 12:
                    next_month = month_start.replace(year=month_start.year + 1, month=1)
                else:
                    next_month = month_start.replace(month=month_start.month + 1)
                
                month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
                month_end_dt = timezone.make_aware(datetime.combine(next_month, datetime.min.time()))
                
                borrow_count = BorrowRecord.objects.filter(
                    borrowed_at__gte=month_start_dt,
                    borrowed_at__lt=month_end_dt
                ).count()
                
                return_count = BorrowRecord.objects.filter(
                    returned_at__gte=month_start_dt,
                    returned_at__lt=month_end_dt,
                    status='returned'
                ).count()
                
                borrow_trend.append({
                    'date': month_start.isoformat(),
                    'count': borrow_count
                })
                
                return_trend.append({
                    'date': month_start.isoformat(),
                    'count': return_count
                })
                
                current = next_month
        
        # 状态分布统计
        status_stats = BorrowRecord.objects.values('status').annotate(
            count=Count('id')
        )
        
        status_distribution = {
            item['status']: item['count']
            for item in status_stats
        }
        
        return JsonResponse({
            'period': period,
            'days': days,
            'summary': {
                'total_borrows': total_borrows,
                'total_returns': total_returns,
                'current_borrows': current_borrows,
                'overdue_count': overdue_count,
                'total_fines': float(total_fines)
            },
            'borrow_trend': borrow_trend,
            'return_trend': return_trend,
            'status_distribution': status_distribution
        })
    
    except ValueError as e:
        return JsonResponse({
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': f'参数错误: {str(e)}'
            }
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': f'统计计算失败: {str(e)}'
            }
        }, status=500)


@require_http_methods(["GET"])
@login_required
def dashboard_summary(request):
    """
    Dashboard概览统计API
    
    URL: GET /api/reports/summary
    权限: admin
    返回: 系统核心指标概览（用于Dashboard首页快速展示）
    """
    if not _check_admin_permission(request.user):
        return JsonResponse({
            'error': {
                'code': 'FORBIDDEN',
                'message': '无权限访问此接口'
            }
        }, status=403)
    
    try:
        # 图书统计
        total_books = Book.objects.count()
        total_copies = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
        available_copies = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
        
        # 用户统计
        total_users = User.objects.count()
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_users = User.objects.filter(
            borrow_records__borrowed_at__gte=thirty_days_ago
        ).distinct().count()
        
        # 借阅统计
        current_borrows = BorrowRecord.objects.filter(status='borrowed').count()
        overdue_count = BorrowRecord.objects.filter(status='overdue').count()
        
        # 今日统计
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_borrows = BorrowRecord.objects.filter(borrowed_at__gte=today_start).count()
        today_returns = BorrowRecord.objects.filter(
            returned_at__gte=today_start,
            status='returned'
        ).count()
        
        return JsonResponse({
            'books': {
                'total': total_books,
                'total_copies': total_copies,
                'available_copies': available_copies,
                'borrowed_copies': total_copies - available_copies
            },
            'users': {
                'total': total_users,
                'active': active_users
            },
            'borrows': {
                'current': current_borrows,
                'overdue': overdue_count,
                'today_borrows': today_borrows,
                'today_returns': today_returns
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': f'统计计算失败: {str(e)}'
            }
        }, status=500)
