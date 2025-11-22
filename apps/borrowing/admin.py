from django.contrib import admin
from .models import BorrowRecord, FineRule


@admin.register(FineRule)
class FineRuleAdmin(admin.ModelAdmin):
    list_display = ("loan_period_days", "max_renewals", "daily_fine")


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "status", "borrowed_at", "due_at", "returned_at", "renew_count", "fine_amount")
    list_filter = ("status", "borrowed_at")
    search_fields = ("user__username", "book__title", "book__isbn")

# Register your models here.
