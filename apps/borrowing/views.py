from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from apps.library.models import Book
from .models import BorrowRecord, FineRule
from apps.accounts.models import User
import json


MAX_LOAN_DAYS = 60
MAX_RENEW_DAYS = 30


def _get_rule() -> FineRule:
    rule = FineRule.objects.first()
    if not rule:
        rule = FineRule.objects.create()
    return rule


def demo(request):
    """借阅演示页面，显示借阅/归还/续借表单和当前用户的借阅记录"""
    user = request.user
    borrow_records = []
    now = timezone.now()
    
    if user.is_authenticated:
        # 获取当前用户的所有借阅记录，按借出时间倒序排列
        # 使用select_related优化查询，同时加载book和user信息
        if user.role == 'admin' or user.is_superuser:
            # 管理员可以查看所有借阅记录
            borrow_records = BorrowRecord.objects.all().select_related('book', 'user').order_by('-borrowed_at')
        else:
            # 普通用户只能查看自己的借阅记录
            borrow_records = BorrowRecord.objects.filter(user=user).select_related('book', 'user').order_by('-borrowed_at')
    
    rule = _get_rule()

    return render(request, 'borrowing/demo.html', {
        'borrow_records': borrow_records,
        'now': now,
        'is_admin': user.is_authenticated and (user.role == 'admin' or user.is_superuser),
        'rule': rule,
    })


@require_POST
@transaction.atomic
def borrow(request):
    isbn = request.POST.get('isbn', '').strip()
    user: User = request.user
    if not user.is_authenticated:
        messages.error(request, '请先登录。')
        return redirect('dashboard_home')

    try:
        book = Book.objects.select_for_update().get(isbn=isbn)
    except Book.DoesNotExist:
        messages.error(request, '未找到该 ISBN 的图书。')
        return redirect('borrowing_demo')

    if book.available_copies <= 0:
        messages.error(request, '该图书当前无可借副本。')
        return redirect('borrowing_demo')

    rule = _get_rule()

    loan_days_raw = request.POST.get('loan_days')
    loan_days = rule.loan_period_days
    if loan_days_raw:
        try:
            requested_days = int(loan_days_raw)
            if requested_days <= 0:
                raise ValueError
            loan_days = min(requested_days, MAX_LOAN_DAYS)
        except ValueError:
            messages.warning(request, '借阅时长输入无效，已使用默认时长。')
            loan_days = min(rule.loan_period_days, MAX_LOAN_DAYS)
    else:
        loan_days = min(rule.loan_period_days, MAX_LOAN_DAYS)

    due_at = timezone.now() + timezone.timedelta(days=loan_days)

    BorrowRecord.objects.create(
        user=user,
        book=book,
        borrowed_at=timezone.now(),
        due_at=due_at,
        status='borrowed',
    )
    book.available_copies -= 1
    book.save(update_fields=['available_copies'])
    messages.success(request, f'借阅成功，应还日期：{due_at.date()} (共 {loan_days} 天)')
    return redirect('borrowing_demo')


@require_POST
@transaction.atomic
def return_book(request):
    record_id = request.POST.get('record_id', '').strip()
    user: User = request.user
    if not user.is_authenticated:
        messages.error(request, '请先登录。')
        return redirect('dashboard_home')

    # 验证输入：必须是数字
    if not record_id:
        messages.error(request, '请输入借阅记录ID。')
        return redirect('borrowing_demo')
    
    if not record_id.isdigit():
        messages.error(request, f'借阅记录ID必须是数字，您输入的是：{record_id}。请检查是否误输入了ISBN。')
        return redirect('borrowing_demo')

    try:
        # 允许归还"借出"和"逾期"状态的记录
        record = BorrowRecord.objects.select_for_update().select_related('book').get(
            id=int(record_id),
            user=user,
            status__in=['borrowed', 'overdue']
        )
    except BorrowRecord.DoesNotExist:
        messages.error(request, f'未找到ID为 {record_id} 的可归还记录。请确认记录ID是否正确，且该记录属于您。')
        return redirect('borrowing_demo')
    except ValueError:
        messages.error(request, f'借阅记录ID格式错误：{record_id}。请输入有效的数字ID。')
        return redirect('borrowing_demo')

    now = timezone.now()
    record.returned_at = now
    if now > record.due_at:
        rule = _get_rule()
        days = (now.date() - record.due_at.date()).days
        record.fine_amount = Decimal(days) * rule.daily_fine if days > 0 else Decimal('0.00')
        record.status = 'returned'
    else:
        record.status = 'returned'
    record.save()

    book = record.book
    book.available_copies += 1
    book.save(update_fields=['available_copies'])
    messages.success(request, '归还成功。')
    return redirect('borrowing_demo')


@require_POST
@transaction.atomic
def renew(request):
    record_id = request.POST.get('record_id', '').strip()
    user: User = request.user
    if not user.is_authenticated:
        messages.error(request, '请先登录。')
        return redirect('dashboard_home')

    # 验证输入：必须是数字
    if not record_id:
        messages.error(request, '请输入借阅记录ID。')
        return redirect('borrowing_demo')
    
    if not record_id.isdigit():
        messages.error(request, f'借阅记录ID必须是数字，您输入的是：{record_id}。请检查是否误输入了ISBN。')
        return redirect('borrowing_demo')

    try:
        record = BorrowRecord.objects.select_for_update().get(id=int(record_id), user=user, status='borrowed')
    except BorrowRecord.DoesNotExist:
        messages.error(request, f'未找到ID为 {record_id} 的可续借记录。请确认记录ID是否正确，且该记录属于您且状态为"借出"。')
        return redirect('borrowing_demo')
    except ValueError:
        messages.error(request, f'借阅记录ID格式错误：{record_id}。请输入有效的数字ID。')
        return redirect('borrowing_demo')

    rule = _get_rule()
    if record.renew_count >= rule.max_renewals:
        messages.error(request, '超过最大续借次数。')
        return redirect('borrowing_demo')

    if timezone.now() > record.due_at:
        messages.error(request, '逾期记录不可续借，请先归还。')
        return redirect('borrowing_demo')

    additional_days = min(rule.loan_period_days, MAX_RENEW_DAYS)
    record.due_at = record.due_at + timezone.timedelta(days=additional_days)
    record.renew_count += 1
    record.save(update_fields=['due_at', 'renew_count'])
    messages.success(request, f'续借成功，新增 {additional_days} 天。')
    return redirect('borrowing_demo')


def _check_admin_permission(user):
    """检查用户是否为管理员"""
    if not user.is_authenticated:
        return False
    return user.role == 'admin' or user.is_superuser


@require_http_methods(["GET", "PUT"])
@login_required
def fine_rule_api(request):
    """
    罚款规则查询/更新API
    
    URL: GET /api/rule, PUT /api/rule
    权限: admin
    """
    if not _check_admin_permission(request.user):
        return JsonResponse({
            'error': {
                'code': 'FORBIDDEN',
                'message': '无权限访问此接口'
            }
        }, status=403)
    
    rule = _get_rule()
    
    if request.method == 'GET':
        return JsonResponse({
            'daily_fine': float(rule.daily_fine),
            'max_renewals': rule.max_renewals,
            'loan_period_days': rule.loan_period_days
        })
    
    elif request.method == 'PUT':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            if 'daily_fine' in data:
                rule.daily_fine = Decimal(str(data['daily_fine']))
            if 'max_renewals' in data:
                rule.max_renewals = int(data['max_renewals'])
            if 'loan_period_days' in data:
                rule.loan_period_days = int(data['loan_period_days'])
            
            rule.save()
            
            return JsonResponse({
                'success': True,
                'daily_fine': float(rule.daily_fine),
                'max_renewals': rule.max_renewals,
                'loan_period_days': rule.loan_period_days
            })
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return JsonResponse({
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': f'参数错误: {str(e)}'
                }
            }, status=400)


@login_required
def overdue_management(request):
    """
    逾期记录管理页面
    
    权限: admin
    """
    if not _check_admin_permission(request.user):
        messages.error(request, '无权限访问此页面')
        return redirect('dashboard_home')
    
    now = timezone.now()
    
    # 获取所有逾期记录
    overdue_records = BorrowRecord.objects.filter(
        status='overdue'
    ).select_related('user', 'book').order_by('-due_at')
    
    # 获取即将逾期的记录（3天内到期）
    soon_due = BorrowRecord.objects.filter(
        status='borrowed',
        due_at__lte=now + timezone.timedelta(days=3),
        due_at__gt=now
    ).select_related('user', 'book').order_by('due_at')
    
    # 统计信息
    total_fine = sum(record.fine_amount for record in overdue_records)
    rule = _get_rule()
    
    return render(request, 'borrowing/overdue.html', {
        'overdue_records': overdue_records,
        'soon_due': soon_due,
        'total_fine': total_fine,
        'overdue_count': overdue_records.count(),
        'rule': rule,
        'now': now
    })


@require_POST
@login_required
@transaction.atomic
def return_overdue(request):
    """
    归还逾期记录（管理员专用）
    
    权限: admin
    """
    if not _check_admin_permission(request.user):
        messages.error(request, '无权限执行此操作')
        return redirect('dashboard_home')
    
    record_id = request.POST.get('record_id', '').strip()
    
    if not record_id or not record_id.isdigit():
        messages.error(request, '无效的记录ID')
        return redirect('overdue_management')
    
    try:
        record = BorrowRecord.objects.select_for_update().select_related('book').get(
            id=int(record_id),
            status='overdue'
        )
    except BorrowRecord.DoesNotExist:
        messages.error(request, f'未找到ID为 {record_id} 的逾期记录')
        return redirect('overdue_management')
    
    now = timezone.now()
    record.returned_at = now
    record.status = 'returned'
    record.save()
    
    book = record.book
    book.available_copies += 1
    book.save(update_fields=['available_copies'])
    
    messages.success(request, f'归还成功。罚款金额: {record.fine_amount} 元')
    return redirect('overdue_management')

# Create your views here.
