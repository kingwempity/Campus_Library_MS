from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "role", "student_id", "email", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "student_id", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("个人信息", {"fields": ("first_name", "last_name", "email", "student_id", "phone", "role")}),
        ("权限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("重要日期", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role", "student_id", "phone", "email"),
        }),
    )

    def has_add_permission(self, request):
        # 仅管理员/超级用户可在后台创建用户（包含设置初始密码）
        return bool(request.user.is_superuser or getattr(request.user, 'role', '') == 'admin')

    def user_change_password(self, request, id, form_url=''):
        # 仅管理员/超级用户可以修改成员密码
        if not (request.user.is_superuser or getattr(request.user, 'role', '') == 'admin'):
            raise PermissionDenied("只有管理员可以修改成员密码")
        return super().user_change_password(request, id, form_url)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # 图书管理员不可见管理员/超级用户信息
        if request.user.is_superuser or getattr(request.user, 'role', '') == 'admin':
            return qs
        # 非管理员（如 librarian）仅能看到非 admin 且非超级用户
        return qs.exclude(role='admin').exclude(is_superuser=True)

    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        if not base:
            return False
        if request.user.is_superuser or getattr(request.user, 'role', '') == 'admin':
            return True
        # librarian 不可查看管理员/超管
        if obj is not None and (obj.role == 'admin' or obj.is_superuser):
            return False
        return True


# Register your models here.
