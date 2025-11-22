from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from apps.library.models import Book
from .models import BorrowRecord, FineRule
from apps.accounts.models import User


def _get_rule() -> FineRule:
    rule = FineRule.objects.first()
    if not rule:
        rule = FineRule.objects.create()
    return rule


def demo(request):
    return render(request, 'borrowing/demo.html')


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
    due_at = timezone.now() + timezone.timedelta(days=rule.loan_period_days)

    BorrowRecord.objects.create(
        user=user,
        book=book,
        borrowed_at=timezone.now(),
        due_at=due_at,
        status='borrowed',
    )
    book.available_copies -= 1
    book.save(update_fields=['available_copies'])
    messages.success(request, f'借阅成功，应还日期：{due_at.date()}')
    return redirect('borrowing_demo')


@require_POST
@transaction.atomic
def return_book(request):
    record_id = request.POST.get('record_id')
    user: User = request.user
    if not user.is_authenticated:
        messages.error(request, '请先登录。')
        return redirect('dashboard_home')

    try:
        record = BorrowRecord.objects.select_for_update().select_related('book').get(id=record_id, user=user, status='borrowed')
    except BorrowRecord.DoesNotExist:
        messages.error(request, '未找到可归还的记录。')
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
    record_id = request.POST.get('record_id')
    user: User = request.user
    if not user.is_authenticated:
        messages.error(request, '请先登录。')
        return redirect('dashboard_home')

    try:
        record = BorrowRecord.objects.select_for_update().get(id=record_id, user=user, status='borrowed')
    except BorrowRecord.DoesNotExist:
        messages.error(request, '未找到可续借的记录。')
        return redirect('borrowing_demo')

    rule = _get_rule()
    if record.renew_count >= rule.max_renewals:
        messages.error(request, '超过最大续借次数。')
        return redirect('borrowing_demo')

    if timezone.now() > record.due_at:
        messages.error(request, '逾期记录不可续借，请先归还。')
        return redirect('borrowing_demo')

    record.due_at = record.due_at + timezone.timedelta(days=rule.loan_period_days)
    record.renew_count += 1
    record.save(update_fields=['due_at', 'renew_count'])
    messages.success(request, '续借成功。')
    return redirect('borrowing_demo')

# Create your views here.
