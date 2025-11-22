from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from apps.library.models import Book


class FineRule(models.Model):
    daily_fine = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.50'), verbose_name="每日罚金")
    max_renewals = models.PositiveIntegerField(default=1, verbose_name="最大续借次数")
    loan_period_days = models.PositiveIntegerField(default=30, verbose_name="借阅天数")

    class Meta:
        verbose_name = "罚款规则"
        verbose_name_plural = "罚款规则"

    def __str__(self) -> str:
        return f"规则: {self.loan_period_days}天 / 每日{self.daily_fine}"


class BorrowRecord(models.Model):
    STATUS_CHOICES = (
        ("borrowed", "借出"),
        ("returned", "已归还"),
        ("overdue", "逾期"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="borrow_records", verbose_name="用户")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="borrow_records", verbose_name="图书")
    borrowed_at = models.DateTimeField(default=timezone.now, verbose_name="借出时间")
    due_at = models.DateTimeField(verbose_name="应还时间")
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name="归还时间")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="borrowed", db_index=True, verbose_name="状态")
    renew_count = models.PositiveIntegerField(default=0, verbose_name="续借次数")
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name="罚款金额")

    class Meta:
        verbose_name = "借阅记录"
        verbose_name_plural = "借阅记录"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["borrowed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.book} ({self.status})"


# Create your models here.
