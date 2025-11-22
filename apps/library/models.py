from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="书名")
    author = models.CharField(max_length=120, blank=True, verbose_name="作者")
    isbn = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="ISBN")
    publisher = models.CharField(max_length=120, blank=True, verbose_name="出版社")
    category = models.CharField(max_length=80, blank=True, db_index=True, verbose_name="分类")
    total_copies = models.PositiveIntegerField(default=1, verbose_name="馆藏总数")
    available_copies = models.PositiveIntegerField(default=1, verbose_name="可借数量")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "图书"
        verbose_name_plural = "图书"
        indexes = [
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.isbn})"


# Create your models here.
