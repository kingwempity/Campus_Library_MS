"""
逾期标记与罚款计算管理命令

用法：
    python manage.py mark_overdue

功能：
    - 扫描所有应还日期已过但未归还的借阅记录
    - 将状态标记为 'overdue'
    - 根据罚款规则预计算罚款金额
    - 输出统计信息

建议通过定时任务（如cron）每日执行
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from apps.borrowing.models import BorrowRecord, FineRule


class Command(BaseCommand):
    help = '标记逾期记录并计算罚款金额'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要标记的记录，不实际更新数据库',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # 获取罚款规则
        rule = FineRule.objects.first()
        if not rule:
            rule = FineRule.objects.create()
            self.stdout.write(
                self.style.WARNING('未找到罚款规则，已创建默认规则')
            )
        
        # 查找所有应还日期已过但未归还的记录
        overdue_records = BorrowRecord.objects.filter(
            status='borrowed',
            due_at__lt=now
        ).select_related('user', 'book')
        
        total_count = overdue_records.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ 没有逾期记录')
            )
            return
        
        self.stdout.write(f'发现 {total_count} 条逾期记录')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('--dry-run 模式：不会实际更新数据库'))
            for record in overdue_records:
                days = (now.date() - record.due_at.date()).days
                fine = Decimal(days) * rule.daily_fine if days > 0 else Decimal('0.00')
                self.stdout.write(
                    f'  - 记录 #{record.id}: {record.user.username} - {record.book.title} '
                    f'(逾期 {days} 天, 罚款 {fine} 元)'
                )
            return
        
        # 批量更新逾期记录
        updated_count = 0
        total_fine = Decimal('0.00')
        
        with transaction.atomic():
            for record in overdue_records:
                days = (now.date() - record.due_at.date()).days
                fine = Decimal(days) * rule.daily_fine if days > 0 else Decimal('0.00')
                
                record.status = 'overdue'
                record.fine_amount = fine
                record.save(update_fields=['status', 'fine_amount'])
                
                updated_count += 1
                total_fine += fine
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ 成功标记 {updated_count} 条逾期记录，总罚款金额: {total_fine} 元'
            )
        )

