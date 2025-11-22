from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """自定义用户，扩展学生相关字段。
    注意：密码仍使用 Django 内置加密；student_id 等敏感字段后续可引入加密存储。
    """

    ROLE_CHOICES = (
        ("admin", "管理员"),
        ("student", "学生"),
        ("librarian", "图书管理员"),
    )

    student_id = models.CharField(max_length=32, blank=True, db_index=True, verbose_name="学号")
    phone = models.CharField(max_length=20, blank=True, verbose_name="手机号")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="student", verbose_name="角色")

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self) -> str:
        return f"{self.username}"

    def save(self, *args, **kwargs):
        # 超级用户强制视为系统管理员角色，避免“超级管理员显示为学生”的歧义
        if self.is_superuser and self.role != "admin":
            self.role = "admin"
        super().save(*args, **kwargs)


# Create your models here.
